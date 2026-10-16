Two channels per sender: DAPHNE-M2-004 continuation test
======================================================

The 256-CAL2 build produced consecutive 256-sample self-trigger frames with
continuation enabled on eight channels. Runs 45373 (off) and 45374 (on) used
channels 0,1 / 8,9 / 16,17 / 24,25, corresponding to the four senders on two
physical links. The other 24 channels produced no record increments. Each
hardware burst lasted 0.5 s; the analysis selects complete 5 ms DAQ windows.

Configuration
-------------

* Firmware identity 0x093e0579, source 93e05798ac1680b254760146974e95891863d2eb.
* Source IDs 804,805,806,807; wire stream IDs 0,1,64,65.
* Enabled mask 0x03030303; software trigger mask 0; source selector 2 (self only).
* CAL2 mask 0: timing-only calibration mode would suppress continuation.
* Offset DAC 2250, VGAIN 2500 on all four firmware AFEs; no detector-bias increase.
* Correlation threshold 1. This is a correlation code, not an ADC amplitude.
* Continuation residual threshold 2 ADC counts, quiet-sample limit 32.
* Continuation register 0x00200002 (off) or 0x80200002 (on), per selected channel.
* Signal-delay overlap 0 for both points, avoiding the legacy overlap setting.
* Both TCReadoutMap and PDS SubdetectorReadoutWindowMap use 312500 ticks before
  the trigger and 0 after at 62.5 MHz; random DAQ window requests are 10 Hz.
* No GIB/BOREAS periodic source was started. SSP LEDs remained disabled; these
  are noisy electronics self-triggers, not optically driven detector pulses.

Results
-------

============================= =============== ===============
Observation                   Off, run 45373    On, run 45374
============================= =============== ===============
Hardware packets, all 8         553787           736982
Hardware continuation packets 0                687832
Hardware busy rejections      184581           0
Hardware full rejections      0                0
Hardware continuation drops   0                0
Selected complete DAQ windows 2                3
Selected decoded frames       11401            19207
Selected continuation frames  0                17300
Continuation links with gap   N/A              0 /17287
Longest observed linked run   1 frame          391 frames
============================= =============== ===============

Every observed continuation link with a preceding frame in its selected window
has exactly 256 ticks between first-sample timestamps: 4.096 us. The 13 additional
continuation frames begin channel/window sequences whose predecessors lie
outside that selected window. The longest observed linked run spans 100096
samples / 1.601536 ms; readout boundaries can truncate longer physical chains.

All selected frames pass format, exact stream-ID, channel, normal calibration-
tag and timestamp checks. ADC unpacking was cross-checked against the official
frame decoder for every selected channel in every selected window. All selected
samples were decoded:2,918,656 (off) and4,916,992 (on), with no observed clipping
at 0 or 16383. The selected PDS fragments have status 0. Sparse/empty requests
outside the bounded burst retain their original DAQ statuses and are excluded
from this complete-window analysis.

Measured trigger accounting closes independently on all eight channels:
trigger edges = seed packets + covered-trigger decisions + busy + full.
Merged triggers are deliberately coalesced into existing chains; packet/trigger
ratios must not be reported as detector efficiency.

The very low residual threshold exhausts the five-peak descriptor budget in
6509 of 19207 selected on frames. Descriptor overflow is distinct from loss of
the raw 256-sample payload. The raw data remain available for further analysis.
The waveform plot uses a selected long-chain excerpt for the on column; it does
not imply that all of the burst was one uninterrupted chain.

Run 45372 is diagnostic only. Its TC map was 5 ms while PDS detector maps still
requested 2 s, causing partial/timeout flags and repeated data across requests.
Both maps were corrected before 45373/45374. Historical files remain on CERN
storage; they do not enter this qualified comparison.

Final state
-----------

DAQ is stopped/configured with no applications in error. The eight selected
channels remain enabled and configured with continuation on and threshold 1,
but all 32 channels are paused/drained (pause mask 0xffffffff). Endpoint 0x16 is
clock-locked in state 8 with valid timestamps. SSP LEDs and both owned periodic
generators are off. Final register and source checks are in evidence/.

Files and recovery
------------------

* evidence/summary.json: quantitative result and qualification limits.
* evidence/daq/: complete-window receipts/statistics, decoded ADC excerpts,
  original HDF5 paths and hashes, and chain-length observations.
* evidence/burst-*.json: hardware snapshots and per-channel counter differences.
* figures/: waveform comparison as PNG and standalone PDF.
* code/: the executed board driver, read-only decoder and extraction/plot tools.
* firmware-reference/: register/admission RTL from the exact loaded source pin.
* campaign-configuration-r2.tar.gz: corrected CERN configuration, environment,
  launch helpers, plans, decoder and analog-readiness record.
* manifest.json: hashes of the archived files. Large HDF5 and waveform .bin files
  remain on CERN storage, not in Git.

The host campaign is:
/nfs/home/np04daq/vst/daphne-m2-004-continuation-2ch-20261016
The dedicated DAQ session is pds-vst-m2-004-continuation-2ch-r2.

For erased board or host environment assets, first follow
../../../deployments/cern-daphne-m2-004/20261016/RESTORE.rst from this directory
(the repository path is deployments/cern-daphne-m2-004/20261016/RESTORE.rst).
This measurement archive adds the tested self-trigger configuration to that
baseline. Only unpack the configuration into a missing, authorized destination
at the original absolute path; compare an existing destination before changing
it. The snapshot alone does not recreate the base OS, CERN CVMFS or compiled
workarea packages. A full destructive restore was not performed for this test.

Repeat the bounded experiment after DAQ boot/conf and endpoint readiness:

1. Use the corrected configuration and verify both kinds of window maps before
   starting a new run. Keep all four source IDs even with only two channels each.
2. Transfer code/board-continuation-test.py to the board under a new recorded
   path. Run its --mode prepare with a fresh --output JSON name. It selects the
   eight channels, clears CAL2 mask, programs threshold/continuation controls,
   and leaves all channels paused. It validates the pinned identity first.
3. Apply the offset/VGAIN settings with code/prepare-analog.sh in the matching
   CERN environment. Use a new metadata output name to retain prior evidence.
4. Start a new TEST run and wait for DAQ running. On the board run the driver
   with --mode burst --continuation 0 --duration 0.5 and a fresh --output name.
   The syntax uses separate arguments, for example:

   python3 board-continuation-test.py --mode burst --continuation 0 --duration 0.5 --output /tmp/NEW-off.json

   Run it with the required board privilege. It pauses/drains in cleanup.
5. Stop DAQ, then take a separate run using --continuation 1 (separate arguments:
   --continuation 1). Record the actual run IDs; do not reuse 45373/45374 as new
   metadata. Both bursts use the same thresholds and analog settings.
6. Adapt code/analyze-continuation.py arguments --run, --label, --continuation
   to the new runs and unused result paths. Require complete status 0 four-source
   windows, then compare hardware losses, timestamp spacing, descriptors and ADC
   samples. The archived script retains the original absolute campaign path;
   update it consistently if the campaign is relocated.
7. Verify pause/drain, endpoint readiness, SSP-off state and stopped DAQ before
   finishing. Preserve failed attempts separately rather than weakening checks.

This result is a bounded electronics/transport characterization, not a detector
response calibration or a sustained full-board bandwidth qualification.
