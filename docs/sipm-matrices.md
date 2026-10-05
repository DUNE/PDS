# SiPM calibration matrices in PDS

PDS runs the scan while the DAQ stays configured and running. DAPHNE and SSP
remain separate hardware systems. This adds no CCM implementation or server-side
scan state; the PDS controller owns ordering, acknowledgements and dataset labels.

| Axis | System | Scope and units |
| --- | --- | --- |
| `vgain` | DAPHNE | Shared AFE gain DAC, code 0..4095 |
| `sipm_bias` | DAPHNE | Shared AFE detector-bias DAC, code 0..4095 |
| `offset`, `trim` | DAPHNE | Selected-channel DACs, code 0..4095; explicit `gain` flag |
| `led_bias_270nm`, `led_bias_367nm` | SSP | LED drive DAC code 0..4095 |
| `led_width_ticks`, `led_second_width_ticks` | SSP | Pulse widths, 0..255 ticks |
| `led_double_pulse_delay_ticks` | SSP | Pulse-pair separation, 0..4095 ticks |
| `led_channel_mask` | SSP | Enable mask over SSP register channels 0..11 |

`attenuation` is accepted as a compatibility alias for `vgain`, and `bias` for
`sipm_bias`. Executed settings and matrix coordinates use the canonical names.
Aliased controls cannot form separate axes or overlap fixed settings. LED bias is
an electrical DAC code, not measured optical intensity or photon flux. The optical settings callback must interpret `led_bias_*` as native DAC codes,
rather than legacy percent/intensity labels.

## Build a matrix

`axes` is an ordered Cartesian product; the last axis changes fastest. Any number
of supported axes can be combined. `settings` supplies explicit fixed DAPHNE
values; `illumination.settings` supplies full optical settings. Each point records both
its coordinates and the complete requested settings. Supply optional `context`
for sensor IDs, temperature measurements and setup provenance; these are labels,
not independently verified measurements.

Examples: `configs/calibration/sipm-bias-vgain-afe0.json` contains 135 points
(three illustrative bias codes and vgain 500..2700 in steps of 50).
`configs/calibration/sipm-bias-led-afe0.json` contains 12 points, including LED DAC
zero. Review the illustrative bias codes, selected channels and source IDs for
your setup before acquiring data.

The same mechanism covers vgain × SiPM bias, SiPM bias × LED bias, vgain × LED bias,
offset × vgain, trim × SiPM bias, LED width × LED bias, pulse separation × SiPM bias,
and higher-dimensional combinations. It acquires and labels datasets; it does not
calculate SiPM gain, breakdown voltage, PDE, dark rate or correlated-noise metrics.
Pulse-pair settings must fit the actual waveform placement: a 256-sample frame
spans 4.096 microseconds at 62.5 MHz, so long pulse separations cannot be studied
from a single frame just by increasing the DAQ readout window.

```sh
pds-calibrate plan configs/calibration/sipm-bias-vgain-afe0.json
pds-calibrate run configs/calibration/sipm-bias-vgain-afe0.json \
  --input-dir /path/to/current-daq-run \
  --output-dir /path/to/new-matrix-datasets \
  --journal /path/to/new-matrix.jsonl
```

The plan command requires no hardware access. The CLI executes DAPHNE-only matrices. Optical matrices are planned by the same
command and executed through the coordinator with the existing PDS optical-settings
function, as described below. No DAQ restart is part of the point logic.
One AFE is selected per plan. Shared vgain and SiPM bias affect the entire AFE;
settings transactions pause that AFE, while unrelated AFEs retain their state.

## Exactly 10,000 waveforms per channel

`waveforms_per_channel: 10000` is the default for matrix plans. The collector first
validates a complete stable DAQ window: fragment status, timing tag, continuity,
duplicates, boundary coverage and equal timestamps across channels. It then
exports the first 10,000 common timing events on every selected channel. It rejects
insufficient windows and never fills a short dataset by accepting missing events.

Each `step-NNN.bin` retains complete packed v4 frames. The sidecar records canonical
coordinates, DAPHNE settings, optical settings acknowledgements, received counts,
source-window counts, selected timestamp range, DAQ record/window provenance,
format metadata and SHA256. Only the durable journal's `step_complete` event
accepts a point, after DAPHNE and its own timing-master counters have passed checks.
The DAPHNE counter comparison covers the full timing-source interval, including
commands outside the exported DAQ window.

Examples request 60 kHz, measured at 48.828125 kHz on GIB. Gathering 10,000 events
requires 0.2048 seconds of timing coverage, so their 0.25-second DAQ window leaves
some margin. Configure this window once before scanning; preflight checks it.
The 0.5 Hz DAQ trigger cadence, settling, capture guard and file closure add time.
Higher timing frequency alone does not imply 0.2048-second wall time per point.
The demonstrated high rates were single-channel tests; qualify full-AFE load first.

## Independent timing domains

Both systems use command **7**, from their respective timing masters. The plan
records DAPHNE's `timing.domain` and `illumination.timing.domain` separately.
An equal command ID does not align timestamps or make command/event counts equal.
The coordinator starts/stops only DAPHNE's timing source; it neither schedules nor
validates the LED timing source against DAPHNE's clock. Optical command counts and
timestamps, if supplied as metadata, are retained without cross-domain comparison.
10,000 waveforms is a DAPHNE data count, not a guarantee of 10,000 LED pulses or
illuminated events.

Command 7 remains selected during ordinary calibration. Between points the
controller pauses/drains the selected AFE to change parameters; it never writes
the board command selector. A different DAPHNE command can inhibit its response
to 7 when an explicit alternative triggering mode requires that policy. That
selection belongs to the owner of the mode transition, not automatic scan cleanup.

## Optical settings integration

The calibration logic accepts the existing PDS settings function as a callback:

```python
from pds.calibration.cli import run_scan

run_scan(plan, input_dir, output_dir, journal_path,
         apply_optical=existing_pds_optical_settings)
```

The callback receives the point's optical settings dictionary. It must apply those
values and return `{"verified": True, "settings": requested_settings}` only after
they are active. It can include independent clock-domain telemetry or a control
transaction ID for provenance. Merely editing a configuration file is insufficient
for an acknowledgement. Callback failures or mismatched settings stop the scan,
stop its DAPHNE timing source and leave the affected AFE paused.

PDS pauses the AFE before calling the optical setter, then applies DAPHNE settings,
waits the explicit settling interval and collects a complete stable DAQ window.
It records each system's acknowledgement separately. There is no SSP alignment,
register driver, optical pulse scheduler or new CCM interface in this change.
The optical controller's source ownership and arbitration stay in that existing
system. The scanner never saves or restores old optical or detector parameters.
Only the supplied DAPHNE final state is applied; optical settings remain at the
last explicitly requested point.

## Qualification status

Matrix order, canonical aliases, hardware scopes, 10,000 matched events per channel,
independent timing domains, setting acknowledgements and failure stopping are
covered by software tests. The earlier higher-rate measurements were command 9
single-channel tests; command 7 and full-AFE matrices require hardware qualification.
DAPHNE15 remains in its diagnostic state; this development changes no live settings.
The helper still requires an aligned DAPHNE endpoint and configured command 7
before running the new examples. Optical-driver development and full DAQ/CCM
integration are outside this calibration-logic change.
