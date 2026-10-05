# Timing calibration scans

This is the canonical calibration technique on `marroyav/calibration`.

SC/CCM runs the coordinator. The DAPHNE server forwards hardware access and
stores no scan, previous settings or automatic return policy. The DAQ runs once
through the entire scan; no configuration file is rewritten between points.

The first plan is `configs/calibration/vgain-afe0.json`: firmware AFE 0, vgain
500..2500 inclusive in steps of 100, GIB timing commands at a requested 6000 Hz,
DAQ triggers at 0.5 Hz, and 2-second readout windows. Only channels already
enabled in AFE 0 are selected. Vgain changes the shared AFE gain DAC; offset
changes the selected channel DACs. Settings transactions pause all eight channels
of the affected AFE briefly; other AFEs retain their acquisition state.

The older `thr-scan`, `att-scan`, `offset-scan`, `trim-scan` and `run --mode calibrun`
workflows are deprecated because they restart/reconfigure the DAQ between points.
They remain available for existing setups with a deprecation warning. The runtime
coordinator currently supports vgain and offset; threshold, trim and optical-source
scans need explicit plans and hardware support before migrating.

## Prepare once

Use the DAQ environment with `timing`, `hdf5libs` and `daqdataformats`, install
`.[runtime]`, and add the server's generated Python schemas to `PYTHONPATH`.
The server must include the read-only timing-register extension. CAL2 gateware
and board selector 2 are required. Align the endpoint and select the endpoint
clock through SC/CCM before scanning. The helper checks both conditions and does
not configure clocks, enable channels, reset counters or align hardware.

On the current CERN image, stopping `daphne.service` stops the runtime and reloads
the same gateware on restart, resetting FPGA settings and counters. Treat a server
update as a configuration boundary; SC/CCM must explicitly apply the desired
operating state afterward. No server update is part of a scan step.

Start the DAQ at **0.5 Hz** with **2-second readout windows**, sufficient raw-data
buffer retention, and working transport. Use an output directory for this run.
Arrange frequent file rotation: the collector reads closed `.hdf5` files and
waits up to 60 seconds. An open `.hdf5.writing` file is never read. Configure file
rotation once; avoid making a separate DAQ run for each point.

Check `source_ids` against the running DAQ configuration. The example uses 800
for DAPHNE15's first stream. Reserve GIB generator 1 and command 9 through the
SC/CCM control system. Command 9 must also be the board's timing-command selector.
The helper rejects an active reserved generator or an active matching command.

```sh
pds-calibrate plan configs/calibration/vgain-afe0.json
pds-calibrate run configs/calibration/vgain-afe0.json \
  --input-dir /path/to/current-run \
  --output-dir /path/to/new-calibration-data \
  --journal /path/to/new-calibration.jsonl
```

The plan command needs no hardware libraries. Equivalently, use
`PYTHONPATH=src python3 -m pds.calibration.cli ...` from a checkout.

## Each point

1. Pause and locally drain the AFE, program the explicit DAC codes, and settle.
2. Select the enabled calibration channels for timing commands.
3. Start the periodic timing source; record its actual rate, period and counters.
4. Wait for a complete 2-second DAQ window whose beginning is after the timing
   source started and the capture guard elapsed. Boundary windows are discarded.
5. Export selected timing-tagged v4 frames and validate their timestamps,
   coverage, continuity, channel agreement and fragment status.
6. Stop timing commands, allow the capture tail, pause/drain the AFE, and check
   board capture counters against the master's accepted command count.
7. Append a durable `step_complete` receipt before advancing.

At 6000 Hz nominal, a 2-second window contains about **12000 waveforms per
channel**. The current 62.5 MHz timing generator quantises the requested rate to
62500000/(256*41), about **5954.65 Hz**. Receipts use the actual period, not the
nominal count. DAQ 0.5 Hz is separate from this timing-command rate; a random
DAQ trigger source has a mean interval of two seconds, not a fixed cadence.
Waiting for a complete stable window and file closure can take longer than two
seconds per point. Commands outside the selected DAQ window are not part of
that point's exported dataset.

Each point produces `step-NNN.bin` containing complete 512-byte DAPHNE frames
and `step-NNN.json` with settings, channel counts, DAQ record/window references
and SHA256. The JSONL journal also records hardware acknowledgements, timing and
capture counters, failures and final state. Only `step_complete` entries identify
accepted points; files left by an interrupted or failed point are not accepted.

## Unpacking

HDF5 contains packed detector frames, not a generic array of 14-bit integers.
Our v4 frame has a 64-byte header (DAQ header, DAPHNE header and five peak
descriptors) followed by 448 packed ADC bytes: 256 unsigned 14-bit samples.
Timing calibration uses tag 2. Unpacked ADC values fit in `uint16`, without
rescaling, sign conversion or dropping the original frame metadata.

Decoding belongs in `rawdatautils.unpack.daphneeth`, using the matching
`fddetdataformats` frame definition. PDS owns scan orchestration and labels;
Waffles owns analysis. Do not implement a second bit decoder in either package.
The existing `rawdatautils` C++ binding already produces NumPy `uint16` arrays.
Unpack accepted steps in batches, and retain timestamps/channels alongside ADCs.
Keep the original packed data and the `step_complete` receipt for provenance.

Before using a decoder, verify `fddetdataformats.DAPHNEEthFrame.sizeof() == 512`
and check its results against a known v4 frame. Rebuild `rawdatautils` against
the same `fddetdataformats`; checking the Python frame library alone does not
guarantee that the unpacker's compiled ABI matches. The older CERN work area
currently exposes 968-byte frames and cannot decode these datasets correctly.

The CERN area `/nfs/home/marroyav/workareas/daq/daphne/pds-trigger-dev-20260930`
provides the matching 512-byte frame and unpacker. Source its `env.sh` from that
directory. The step sidecar identifies schema `pds.calibration.step.v1`, frame
version/size, ADC offset/width/count, timing tag and clock frequency explicitly.

Run `python3 tools/benchmark_unpacker.py` in that environment. It checks the
compiled decoder against known frame-accessor values before decoding a batch,
then reports decoder-only throughput. It also rejects a mismatched frame library
or unpacker before using the large pointer/count batch API.

Benchmark the compatible C++ unpacker separately from HDF5 reading and dataset
selection before adding SIMD. Any AVX2 implementation belongs in `rawdatautils`,
with runtime CPU selection, a scalar fallback and bit-for-bit comparison against
the frame accessors. Waffles should use the shared implementation.

## Final state and interruptions

The supplied plan explicitly ends **paused**, retaining the last vgain code and
calibration selection. SC/CCM can instead supply a final physics configuration:

```json
"final": {
  "mode": "physics",
  "settings": [{"variable": "vgain", "target": 0, "value": 1300}],
  "settle_ms": 100
}
```

1300 is an illustrative final code, not a saved previous value. For offset scans,
set `variable` to `offset`, select the desired channels, supply `gain: true` or
`false`, and specify the requested offset values and final configuration.

On an ordinary error or interrupt, the coordinator stops timing commands and
attempts to leave the affected AFE paused. It never restores analog settings or
returns to physics after failure. A separate timing worker stops on caller EOF
and has a bounded timeout. Killing that worker or losing its host can leave the
hardware generator running; restart reconciliation/watchdog ownership remains
with SC/CCM. An AFE with existing calibration/pause state is rejected until SC/CCM
explicitly reconciles it. Existing journals and dataset directories are never
overwritten, and an ambiguous step is never automatically replayed.

Local locks reserve the board and timing master for the scan on one control
host. They do not provide a distributed lease or stop another control system
from writing the same hardware. Run through one authoritative SC/CCM owner;
coordinated multi-board bursts and distributed recovery are later extensions.

DAPHNE15's GIB command route was verified on 2026-10-05, but the endpoint remained
in state 6 and its clock was local. These helpers deliberately refuse synchronized
calibration acquisition in that state. No analog scan has been qualified yet.

## Tests

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -p test_calibration.py -v
PYTHONPATH=src:/path/to/server/python python3 -m unittest discover -s tests -p 'test_runtime*.py' -v
```
