# Runtime calibration from SC/CCM

SC or CCM owns the scan, arbitration, configurations, timing-command schedule,
metadata and final operating state. The DAPHNE server is a communication bridge:
it forwards settings commands and single runtime-register reads/writes. It does
not own a scan session, poll acknowledgements, save original parameters, choose
an acquisition mode, or restore settings on completion/disconnect/timeout.

The new firmware controls select timing-only channels and pause capture admission
without resetting filters or queued records. The hardware drain status covers
local capture, serialization and packet-store output; it is not a Hermes/DAQ
transmission fence. This path requires CAL2 gateware, the new server bridge RPC,
board xcorr selector 2, and working timing lock/command routing.
Channel enables are at `0x94000020/24`; the timing-command selector is at
`0x94000028`. The corresponding frontend addresses are bitslip controls.
Readout transport must be enabled for local drain to complete. After FPGA/clock
programming, verify the Ethernet PHY reset and lock before starting a scan.

DAPHNE15 with firmware `93e0579` and server `9e1be59` passed live mask,
pause/drain, disconnect persistence and explicit-mode checks on 2026-10-01.
An empty-settings transaction was exercised; analog DAC changes were not tested.
The capture contained all 220 expected software-tagged waveforms. Actual timing
acceptance remains unqualified because the optical endpoint stayed in FSM 6.

Install `.[runtime]` in the SC environment. Add the server build's
`srcs/protobuf` directory to `PYTHONPATH` so its generated v2 Python schemas can
be imported. Create one shared `RuntimeControl` per board inside the authoritative
SC/CCM controller; its board lock serialises mask/settings transactions. Arbitration
between separate SC/CCM processes belongs to their control system, not the server.

```python
from pds.core.runtime import DaphneBridge, RuntimeControl

bridge = DaphneBridge("tcp://BOARD:9876")
sc = RuntimeControl(bridge)
try:
    for step_id, bias in enumerate([1000, 1100], 1):
        ready = sc.configure_afe(
            0, [{"variable": "bias", "target": 0, "value": bias}],
            timing_channels=[0, 1], paused_channels=[2, 3, 4, 5, 6, 7],
            settle_ms=100,
        )
        # SC/CCM records step_id, desired configuration and ready metadata.
        # Issue a finite burst from the timing master, using ready['command_id'].
        # Record the first/last command timestamps in the DAQ timing clock.
        # Wait for the last command's trigger latency and capture window.
        sc.pause_afe(0)
    # The AFE stays paused with its last values and timing selection.
    # SC/CCM decides whether to continue scanning or apply a new operating state.
finally:
    bridge.close()  # Communication closure does not change hardware state.
```

The example DAC values and settling time are illustrative. `configure_afe`
pauses all eight channels in the affected AFE, waits for local drain, forwards
only the supplied settings, waits the requested settling interval, and applies
the explicitly requested timing/pause selections. Unrelated AFEs retain their
masks and continue acquisition. Channel enable bits remain authoritative.

Use firmware/PL IDs: AFE 0..3, channel 0..31, matching waveform headers. The
bridge adapter translates DAC targets to the server's physical board numbering.
Bias and attenuation affect the whole AFE; trim and offset affect one channel
and require an explicit `gain` boolean. Board-global and arbitrary AFE-register
scans need their own SC/CCM scope arbitration. This first helper supports the
four DAC variables above. Settings responses report programmed/cached DAC codes,
not independent analog measurements.

To resume self-trigger with **new** operating values, explicitly request them:

```python
sc.configure_afe(
    0, [{"variable": "bias", "target": 0, "value": 1200}],
    timing_channels=[], paused_channels=[], settle_ms=100,
)
```

An empty settings list keeps the current parameters. An empty timing selection
restores the board xcorr policy for that AFE; it does not restore previous DAC
values. There is no implicit final state. On an operation failure the SC helper
attempts to keep the affected AFE paused and raises the error. It does not undo
parameter writes; SC/CCM supplies the next desired state explicitly.

For many boards, execute their setting transactions concurrently and wait for
all readiness acknowledgements before issuing one shared timing-command burst.
The timing source and DAQ stay configured between steps. Retain channel selection,
complete desired configuration, step IDs, and command timestamps in scan metadata.
Select datasets by channel, timing tag 1, and DAQ timestamps accounting for the
waveform pretrigger interval; delayed old network packets can arrive after drain.
The returned `ready_unix_ns` is a host timestamp, not a DAQ timestamp.

Verification without hardware:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -p test_runtime.py -v
```
