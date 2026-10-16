DAPHNE-M2-004 CERN recovery snapshot, 16 October 2026
===================================================

This directory preserves the operating configuration and installed board
application assets used for the completed 32-channel DAPHNE/SSP exercise.
Read guide/daphne-m2-004-guide.pdf for operation, measured results and limits.
The live hardware was not reconfigured to make this backup.

What is recoverable
-------------------

* campaign/: the original CERN campaign's launchers, cached runtime environment,
  helpers, XML configuration, scan plans, executed scan/SSP/acquisition scripts,
  selected receipts and small analysis/evidence. Earlier attempt scripts and
  draft metadata are historical; the final qualified reference is run45371,
  joint-gain-r4. Do not replay preparation or recovery scripts indiscriminately.
* board/board-rootfs.tar.gz: the three installed FPGA apps, compatible overlays,
  exact daphneServer binary and private libraries, Hermes executable, gateware
  selector/profiles, board identity/network settings, optical-management helper,
  and selected runtime systemd units/drop-ins. board-files.json records every
  captured path, mode, link target, size and regular-file digest.
* protobuf/: generated high/low-level DAPHNE RPC Python modules.
* environment/: Python requirements, original virtual-environment configuration,
  runtime module resolution, workarea constants, nine source revision/dirty-state
  records, tracked patches and selected untracked source files.
* board-server-source-fix.tar.gz: the server frame-monitor fix files, relative to
  DUNE-DAQ/daphne-os commit 258cc46eb8973761fb59641f701c17cbea07f226.
* guide/: the LaTeX operator guide and editable report template, compiled PDFs,
  exported figures and reference scan evidence.

Credentials, Kerberos caches, private keys, the PetaLinux boot/root filesystem,
CVMFS releases, complete DAQ build/install trees, and large raw waveform/HDF5
files are not included. There is no claim of a bare-metal or offline restore.
A compatible board OS and the pinned CERN software/repositories must remain
available or be rebuilt. Original raw-data locations and hashes are retained;
hashes cannot reconstruct erased raw data. The board clock was not used to
establish this snapshot's date.

1. Recover and verify this snapshot
----------------------------------

On an authorized host, clone the PDS repo and select the calibration branch:

::

    git clone --branch marroyav/calibration https://github.com/DUNE/PDS.git PDS-recovery
    cd PDS-recovery/deployments/cern-daphne-m2-004/20261016
    python3 verify.py

Keep the printed commit ID (git rev-parse HEAD) with recovery notes. verify.py
checks all versioned backup files plus the regular members of the board archive.
It only reads files; it does not unpack onto a live system or contact hardware.

2. Restore the CERN campaign at its original absolute path
---------------------------------------------------------

The scripts, XML and cached environment retain absolute CERN paths. First verify
ownership and confirm that this destination is missing. If it exists, compare it
with this snapshot and choose a recovery plan rather than overwriting evidence.
Set backup to the absolute path of this snapshot directory, then run as the
authorized np04daq operator on np04-srv-017:

::

    backup=/absolute/path/to/PDS-recovery/deployments/cern-daphne-m2-004/20261016
    campaign_root=/nfs/home/np04daq/vst/daphne-m2-004-offset2250-all32-20261016
    test ! -e "$campaign_root" || { echo 'Destination exists; stop and inspect'; exit 1; }
    mkdir -p "$campaign_root"
    cp -a "$backup/campaign/." "$campaign_root/"
    mkdir -p "$campaign_root/data/calibration/raw" "$campaign_root/logs/calibration"

The saved receipts refer to the original data, which is not supplied here.
Fresh scans require a new tag and a new DAQ run as described in the guide.
Do not run r4 unchanged: its historical plan/journal already exist.

3. Recreate missing host Python files/environment
-------------------------------------------------

The recorded interpreter is CERN Python 3.12.12 with system-site packages enabled.
The scientific/DAQ bindings are provided by the pinned CERN environment; a generic
pip-only virtual environment is insufficient. Confirm that the fddaq-v5.6.2-a9-1
release and paths in environment/runtime-modules.json are available. Do not modify
an existing shared PDS checkout or virtual environment without coordinating its
owner. The following commands are for missing destinations only:

::

    export PDS_CHECKOUT=/nfs/home/np04daq/calib/control/PDS
    export PDS_PROTOBUF_DIR=/nfs/home/np04daq/calib/control/python
    export PDS_VENV=/nfs/home/np04daq/calib/control/venv
    git clone https://github.com/DUNE/PDS.git "$PDS_CHECKOUT"
    git -C "$PDS_CHECKOUT" checkout 82fa12eeefef2d480fc23e869ad2c9c2bc54017b
    mkdir -p "$PDS_PROTOBUF_DIR"
    cp -a "$backup/protobuf/." "$PDS_PROTOBUF_DIR/"
    source "$campaign_root/runtime-env.sh"
    /cvmfs/dunedaq.opensciencegrid.org/spack/releases/fddaq-v5.6.2-a9-1/.venv/bin/python3 \
        -m venv --system-site-packages "$PDS_VENV"
    "$PDS_VENV/bin/python" -m pip install \
        pip==25.0.1 annotated-doc==0.0.5 pyzmq==27.2.0 shellingham==1.5.4 typer==0.27.3
    "$PDS_VENV/bin/python" -m pip install -e "$PDS_CHECKOUT"
    export PYTHONPATH="$campaign_root:$PDS_PROTOBUF_DIR:$PDS_CHECKOUT/src${PYTHONPATH:+:$PYTHONPATH}"
    "$PDS_VENV/bin/python" -c \
        'import pds,zmq,google.protobuf,numpy,uhal,timing.core,hdf5libs,daqdataformats,fddetdataformats,daphneV3_high_level_confs_pb2'

The editable requirement in python-requirements.txt records the original pin;
the explicit checkout above avoids silently selecting a later runtime. Restore
tracked patches and untracked files from environment/source-state only after
review. The PDS snapshot's local changes concern documentation/operator tools;
board scanning uses the pinned source plus campaign/acquisition_wire_ids.py and
campaign/ssp_routine.py. Generated protobuf modules still need the protobuf
runtime exposed by the recorded CERN environment.

If the DAQ workarea was erased, reconstruct it with the site's DBT workflow at
/nfs/home/marroyav/workareas/daq/daphne/pds-trigger-dev-20260930, using the recorded
base release and every exact source revision in software-provenance.json. Build
and install those packages before attempting imports or DAQ startup. The cached
runtime-env.sh alone cannot recreate missing compiled libraries/schema files.
The site helper /nfs/home/np04daq/bin/web_proxy.sh and drunc's ssh-CERN-kafka.json
remain site dependencies. The helper's only use in launch-daq-cached.sh is '-u'
(proxy unset); if absent, have the DAQ owner replace that call with the appropriate
site proxy-unset operation. This backup does not store site credentials.

4. Restore erased board application/configuration assets
--------------------------------------------------------

These files belong only to DAPHNE-M2-004 (production MAC 00:0A:35:24:05:30).
The archive is an application/configuration snapshot, not an OS image. It includes
absolute symlink targets from the original root filesystem. Inspect it in staging
and compare board/board-files.json before installation. Do not use a generic
archive extraction filter that silently removes these required links.

Transfer board/board-rootfs.tar.gz to /tmp on the board using your authorized
SSH route. Stop DAQ and all scan-owned timing/SSP activity first. Keep serial
access through np04-onl-004 available while restoring network settings. After
confirming the board identity and compatible base OS, a board operator can run:

::

    sudo systemctl stop daphne-runtime.target
    sudo tar --extract --gzip --file=/tmp/board-rootfs.tar.gz \
        --directory=/ --no-same-owner
    sudo systemctl daemon-reload
    sudo systemctl enable daphne-management-optical.service
    sudo /usr/sbin/daphne-gateware set-default self-trigger-256-cal2
    sudo /usr/sbin/daphne-gateware switch self-trigger-256-cal2
    sudo systemctl enable daphne-runtime.target
    sudo /usr/sbin/daphne-gateware status

The archive uses relative member names under the original root; extraction
requires root and intentionally restores those reviewed paths. Network service
activation is a separate operator action: keep the working management connection
until serial/fallback access is confirmed. The captured network files set the
registered CERN management address; reboot persistence was not tested in the
original campaign. Do not reboot solely to validate this backup.

Stop the runtime before restoring its files so stale /run active-profile state
does not describe a still-running old app. The selector's switch must perform a
real runtime start and verify its live identity. Compare all three profile names
with the guide. The remaining low-level tools, FPGA manager, clock hardware
support, /usr/bin/env/python3 and systemd come from the compatible base OS.

5. Qualify the restored system before taking data
-------------------------------------------------

Restore alone does not qualify hardware behavior. Require the 256-CAL2 live
identity 0x093e0579, management connectivity, DAPHNE endpoint 0x16 in locked and
timestamp-valid state8, SSP endpoint readiness, and two ready physical data links.
Check wire IDs 0,1,64,65 and source IDs804..807. Re-initialize the dedicated DAQ
session with launch-daq-cached.sh, boot/conf under the DAQ owner, and inspect its
state. Address the pinned endpoint deskew/resync compatibility issue only under
the conditions documented in the guide. Then take a fresh tagged scan and apply
the same strict data/counter/ADC checks.

Keep SSP and DAPHNE timing domains distinct in reporting: the archived recipe
uses BOREAS_TLU_NP04 for SSP and GIB for DAPHNE with no optical coupling. Shared-
master synchronization and detector response require a separate future test.

Verification limits
-------------------

This snapshot was captured from the working setup, hashed, checked for expected
configuration/source identity, and packaged with syntactically checked scripts.
The guide and report template were compiled and rendered for layout inspection.
A destructive restore onto the live board or deletion/recreation of the CERN
software environment was not performed. Recovery commands are an operator
procedure, not evidence that a complete restoration has already been tested.
