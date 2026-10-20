Operate and recover DAPHNE-14
============================

Read REPORT.rst for tested scope and limits. Do not extract the old M2-004
board-settings archive onto DAPHNE-14: identities and management settings
are different. Verify this package's hashes with python3 verify.py.

Normal operation
----------------

SSH to petalinux@np04-daphne-014.cern.ch and use:

::

  sudo /usr/sbin/daphne-gateware list
  sudo /usr/sbin/daphne-gateware status
  sudo /usr/sbin/daphne-gateware switch self-trigger-256-cal2
  sudo /usr/sbin/daphne-gateware set-default self-trigger-256-cal2

The other installed choices are self-trigger-1024 and full-stream. Stop DAQ
before switching; reconfigure timing and DAQ afterward. Profiles 1024 and
full-stream were installed/verified, not acquisition-tested here.

The saved default OS boots /dev/mmcblk0p3. After a firmware reload or reboot,
run the host-side alignment routine for endpoint 32 before configuring DAQ.
The copied alignment scripts use one-use evidence filenames; choose a new
output filename for each invocation rather than overwriting prior evidence.

config/ contains the runnable XML. The full as-captured archive also contains
inherited draft notes and historical backup files; REPORT.rst records the
completed qualification.

The executing campaign is on np04-srv-017 as np04daq:
/nfs/home/np04daq/vst/daphne14-pds-ta-charge-20261020

Use a new DAQ session name for a fresh launch. The saved launch-daq.sh sources
the shared, pinned runtime from the earlier M2-004 guide campaign. The final
executed session was pds-vst-daphne14-pds-ta-charge-r3, config ID pds-daphne14.
The test requires the descriptor-aware readout packages and the exact
LD_PRELOAD compatibility library at the path recorded in the Session XML.
If restoring a missing library, install the supplied binary at that path
and verify its hash; compare an existing file rather than overwriting it.
The source/build script and the prior CTest log are supplied for rebuilding
against the same release and nlohmann-json 3.12 ABI.

The bounded producer requires root on DAPHNE-14, 256 CAL2 build 0x093E0579,
locked clocks and endpoint address 32/state 8. Upload it after each reboot
because /tmp is volatile. It enables 32 logical channels, disables timing
injection and self-trigger selection, and pauses in its cleanup. Prepare
before run start; run the burst only after DAQ is running and transmit
buffers drain. Per-channel descriptor threshold is 2 ADC, quiet limit 32,
continuation disabled. The scripted burst lasts 10 s. Select a new run and
new evidence filenames; the supplied decoder is specifically pinned to
run 45392 and must be adapted for another run.

Serial and U-Boot rollback
--------------------------

Serial is on np04-onl-004:
/dev/serial/by-id/usb-Xilinx_DAPHNEMezz_FNALDMezz04-if01-port0
at 115200 baud. Stop DAQ and producers before rebooting or resetting.
Catch the U-Boot prompt after a normal Linux reboot. At ZynqMP>:

::

  run daphne14_legacy_bootcmd

That boots the original OS once, with the saved environment still selecting
the newer OS on the following reboot. To make the legacy choice persistent:

::

  setenv bootcmd run daphne14_legacy_bootcmd
  saveenv
  reset

To restore the newer saved choice:

::

  setenv bootcmd run daphne14_trial_bootcmd
  saveenv
  reset

The original root is /dev/mmcblk0p2. The original top-level boot images were
retained. The exact previous/new commands are in boot-rollback.json.
The new OS has no usable MTD/fw_printenv environment path on this board;
use U-Boot for these changes. One observed orderly shutdown waited about
90 seconds for timesyncd; allow for that delay when monitoring serial.

JTAG recovery connection
-----------------------

The verified scan used the CERN installation on np04-onl-004:
/nfs/sw/fpga/Xilinx/Vivado/2024.1/bin/hw_server and xsdb.
A task-owned hw_server was started on tcp:localhost:3121. Verify the cable
name FNAL DAPHNEMezz FNALDMezz04A before any reset/download. Read-only scan:

::

  xsdb -eval 'connect -url tcp:localhost:3121; puts [jtag targets]; puts [targets]; disconnect; exit'

Enumeration is verified. JTAG RAM boot remains an available engineering
procedure, not a successful test result from this campaign. It requires a
compatible FSBL/PMU/BL31/U-Boot set; do not download arbitrary components or
assume a processor reset is equivalent to a complete power cycle.

Rebuild an erased trial root
----------------------------

The reference OS archives and manifest are stored at:
/nfs/home/marroyav/daphne14-os-trial-20261020

Validate their SHA-256 values against reference-os-manifest.json. The
included scripts record the migration that was performed. Creating or
formatting the trial partition was a one-time action; do not rerun it on
an existing populated partition.

Boot the retained legacy OS before restoring the inactive p3 filesystem.
Mount p3 at /mnt/d14trial and stage the two verified archives and manifest
under /tmp/d14-reference. stage-trial-os.sh shows the original extraction,
local credential/SSH preservation, and application checks. It initially
writes the legacy SGMII settings. Before booting the restored filesystem,
apply the hash-verified daphne14-settings-20261020.tar.gz to the mounted
trial root, preserving its /dev/null service-mask symlink. That archive
supplies the corrected optical helper, network identity and timing profile.
The board's private credentials and host keys must come from its retained
legacy filesystem or an authorized replacement process; none are supplied
in this package. Preserve the current machine ID when repairing an existing
installation; generate a distinct one for a new root.

Boot files are under /boot/daphne14-trial-20261020. The reference manifest
hashes both kernel and DTB archives; final-board-status.log records the
individual file hashes. Verify those files before selecting the trial
boot command. This procedure does not repair erased QSPI boot firmware.
