# GIB timing-command rate test, 2026-10-05

GIB delivered timing commands above 6 kHz to DAPHNE15. Across nine short
single-channel tests, all 42,386 accepted commands produced captured waveforms;
master rejections and DAPHNE busy/full increments were zero at every point.

| Requested kHz | Measured kHz | Captured waveforms |
| ---: | ---: | ---: |
| 6 | 5.812872 | 5876 |
| 10 | 9.765625 | 5784 |
| 20 | 18.780048 | 5586 |
| 40 | 34.877232 | 5221 |
| 60 | 48.828125 | 4913 |
| 100 | 81.380208 | 4183 |
| 130 | 81.380208 | 4175 |
| 200 | 122.070313 | 3322 |
| 244 | 122.070313 | 3326 |

## Conditions and measurement

DAPHNE15 firmware `93e0579`, server `258cc46`; GIB generator 1, periodic command
9, 62.5 MHz timing clock. Firmware channel 0 received timing commands with remote
clock selected and continuation disabled. Each waveform contained 256 samples
in a 512-byte v4 DAPHNE Ethernet frame, with timing tag 2.

For each point, the controller read board counters, started the bounded timing
source, sampled master accepted/rejected counters and timestamps, stopped the
source, and read board counters after a 25 ms tail. Target duration was
`max(25 ms, 6000 / helper_reported_rate_hz)`; the helper error below means these
were not exactly 6000-command bursts. Packets were captured directly on
np02-srv-001 through DPDK, rather than a triggered DAQ HDF5 run.

Measured rates above use `62500000 / timestamp_spacing_ticks`. Every adjacent
waveform timestamp within a point had the same spacing. Each point's accepted
master count, DAPHNE record increment, captured waveform count and unique
timestamp count matched. Independent master counter/time measurements agreed
within their sampling uncertainty.

122.070313 kHz is the highest demonstrated rate, not a measured absolute limit.
This short single-channel result does not establish sustained full-AFE/full-board
or DAQ bandwidth. The endpoint remained in state 6; timing alignment is unqualified.
No analog settings changed. The controller stopped its generator, disabled readout
links, restored routing, and returned to local clock and calibration mask 0.
Clock switching reset capture counters; the saved point deltas precede that reset.

## Frequency metadata caveat

The helper used for this test calculated period as `256 * prescale * 2**divisor`.
For all tested settings, divisor was 0 and measured period was instead
`256 * (prescale + 1)`. Thus the raw `started.actual_rate_hz` and `period_ticks`
fields are erroneous calculated metadata, retained unchanged in
[results.jsonl](results.jsonl). Use [rates.csv](rates.csv), whose `observed_hz`
and `period_ticks` come from captured waveform timestamps. This measurement
reference does not change the helper implementation or qualify other divisors.

## Saved evidence

[rates.csv](rates.csv) contains measured frequencies and counter totals for plotting.
[results.jsonl](results.jsonl) retains original per-point master and board snapshots.
The complete packet audit, scripts, state snapshots and PCAP remain on CERN NFS:

```text
/nfs/home/marroyav/workareas/daq/daphne/timing-rate-20261005/
```

PCAP file: `rates.pcap`; SHA-256: `9aa27dc7a50e67af2305c3a9164f37a02f8eb51dfbdd6abe32f850323729e760`.
