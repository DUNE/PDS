DAPHNE-14 deployment and PDS-trigger DAQ test, 20 October 2026
============================================================

DAPHNE-14 now boots the same PetaLinux 2026.1 userspace and Linux
6.18.10-xilinx-g6627b6ab1760 kernel as M2-004, with its own network/SSH
identity. The default and active gateware is self-trigger-256-cal2,
ABI 2.0, build 0x093E0579. The 1024 self-trigger and full-stream profiles
are installed and pass profile verification; those modes were not run.

The deployed OS is a hash-verified export of M2-004's running filesystem,
not a separately rebuilt or qualified release. Credentials, SSH keys,
machine identity and active board/network settings were excluded from the
reference export. DAPHNE-14 retained its own credentials and host keys;
its generated machine ID was checked to differ from M2-004's.

Board and recovery state
------------------------

* Management: np04-daphne-014.cern.ch, 10.73.137.160/24,
  ba:be:ba:d1:cb:ff. This MAC is the preserved observed legacy runtime
  value, not a newly established SOM factory identity.
* New root: /dev/mmcblk0p3, 8 GiB. Old root /dev/mmcblk0p2 and original
  /boot/Image, system.dtb and ramdisk remain available.
* New boot files: /boot/daphne14-trial-20261020/Image and system.dtb.
  U-Boot bootcmd now runs daphne14_trial_bootcmd. Saving this environment
  and a subsequent reset/autoboot were verified over serial.
* The existing QSPI 2024.1 FSBL/BL31/U-Boot firmware was retained. Only its
  boot environment was saved. The copied Linux fw_env configuration
  cannot initialize this board's environment; daphne-boot-ok.service is
  masked. Use the verified serial U-Boot path for boot selection.
* Serial/JTAG host: np04-onl-004. UART is
  usb-Xilinx_DAPHNEMezz_FNALDMezz04-if01-port0, 115200 baud.
  JTAG scan identifies FNAL DAPHNEMezz FNALDMezz04A, xck26 and arm_dap;
  XSDB sees all four running A53 cores. JTAG enumeration was tested;
  RAM boot and a JTAG-forced reset were not exercised in this deployment.
* New-kernel management Ethernet needs optical 1000BASE-X configuration:
  clear GEM NCFGR bit 27, advertise 0x20, enable/restart PCS negotiation.
  The preserved legacy SGMII settings produced no RX packets. The
  target settings archive contains the working service and helper.
* PL I2C is bus 1 after migration; identify it by 9c000000.i2c rather
  than assuming bus 2. The clock-chip service discovers the bus.
* Endpoint 0x20 reaches state 6 after boot initialization; targeted GIB
  alignment plus deskew-done command 3 brings it to state 8 with valid
  timestamps. It was realigned after the saved-boot verification.
* Final state: all runtime services healthy, endpoint state 8, all 32
  channels paused, no DAQ run or test producer left running.

Optical checks after migration: timing RX -13.49 dBm; DAQ0 -1.93 dBm;
DAQ1 -2.69 dBm. All three EEPROM checksums pass and RX LOS is false.
Both data transmitters are enabled. Timing TX disable is expected for the
receive-only timing path. The data-sender test configuration uses the
existing private test addressing and is scoped to this one-board exercise;
this is not a qualified simultaneous multiboard network configuration.

Functional result: run 45392
----------------------------

The live DAQ used fddaq-v5.6.2-a9-1 and the existing custom descriptor-aware
readout packages. The user-supplied v5.7.1 configurations were references;
the executing DAQ release was not upgraded to v5.7.1. Source revisions and
dirty-state/diff hashes are in evidence/source-provenance.json.

Two physical links, four senders, eight channels per sender were enabled.
A bounded software-capture producer sent 200 writes at 20 Hz over 9.95 s.
Each of the 32 channels accepted 200 records: 6400 records total. Busy and
full counters did not increase during that burst. These are hardware
acceptance counts, not a claim that every waveform was saved by the DAQ.

The trigger path was:

  DAPHNE descriptors -> PDS TPs -> TAMakerPrescaleAlgorithm (100)
  -> PDS TAs -> TCMakerPrescaleAlgorithm (1) -> MLT -> PDS + charge requests.

The standard v1.6.0 TA prescale implementation assumes TPC timing/type.
This session preloads the saved compatibility library, which uses PDS type
and one-tick sample units for detector 8 and preserves the standard TPC
behavior otherwise. Its CTest checks cover type, timestamp scaling,
prescaling, preserved inputs and rejection of zero-duration PDS TPs.
No installed system library was replaced.

No standalone random TC maker was enabled. Charge was an all-zero WIBEth
FDFakeReaderModule stream with TP/TA generation disabled; it supplied
readout data and could not provide the tested trigger source. Its raw
processor has the schema-required processing-step entry even though
postprocessing is disabled. Both module generation and configuration
consolidation pass.

The official decoders verified all 29 saved trigger records:

* Every record contains all four PDS sources 800--803, all 32 channels,
  eight channels per sender, 256 ADC samples per frame and expected wire IDs.
* Every record contains nonempty emulated charge source 900. Charge frame
  timestamps step by 2048 ticks and cover the requested window.
* PDS and charge use the same 62500-tick (1 ms) window, with zero fragment
  status flags for every PDS and charge fragment.
* Saved TAs are type kPDS, detector 8; TCs are kPrescale, detector 8.
  Each TC timestamp matches a saved TA activity timestamp. Both readout
  edges equal the TC timestamp +/-31250 ticks.
* Saved PDS payload totals 928 frames, 29 frames per channel.
* 28 records have zero status flags on every fragment. The first record's
  TC metadata fragment has status 18; its candidate payload is present and
  decodes, and its PDS/charge fragments are complete. No interpretation or
  resolution of that metadata boundary flag is claimed.

The data demonstrate PDS-TA-driven PDS and emulated-charge windows in the
DAQ. They do not establish response to detector light, a physical charge
trigger, SSP synchronization, physics efficiency, sustained throughput or
loss-free acquisition beyond the bounded acceptance observation. SSPs were
not commanded. All applications stopped and shut down with exit code 0.

Data and reproducibility
------------------------

CERN campaign:
/nfs/home/np04daq/vst/daphne14-pds-ta-charge-20261020

Raw HDF5: data/calibration/raw/*run045392*.hdf5 beneath that campaign.
The decoded evidence includes every input path and SHA-256 digest.

Persistent OS artifacts (not stored as large Git objects):
/nfs/home/marroyav/daphne14-os-trial-20261020

Reference rootfs archive SHA-256:
13502f238e9099f342dec30be6dbdacd8fbf3acae567142f61639261584a88a5

Reference boot archive SHA-256:
9adf58d537f2dc28060f01902bc8bae04b0a060138f15b6681ed39042a2c2404

The package contains the actual DAQ configuration, analysis, bounded
producer, migration commands, target settings, compatibility library and
source, selected execution logs and hashed evidence. It excludes passwords,
SSH keys, Kerberos caches and raw waveform/HDF5 data. The OS archives on NFS
are runtime snapshots; the repository's earlier M2-004 backup supplies the
shared runtime/environment reconstruction context. There is no bare-metal
recovery claim for an erased QSPI or lost credentials.
