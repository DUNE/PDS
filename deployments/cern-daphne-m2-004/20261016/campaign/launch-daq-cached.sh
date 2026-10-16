#!/bin/bash
set -e
root=/nfs/home/np04daq/vst/daphne-m2-004-offset2250-all32-20261016
source "$root/session.env"
source "$root/runtime-env.sh"
export DUNE_DAQ_BASE_RELEASE=fddaq-v5.6.2-a9-1
export SPACK_RELEASES_DIR=/cvmfs/dunedaq.opensciencegrid.org/spack/releases
export VST_DAQ_DB_PATH="$DUNEDAQ_DB_PATH"
source "$root/helpers.bash"
vst_use calibration
source /cvmfs/dunedaq.opensciencegrid.org/spack/releases/fddaq-v5.6.2-a9-1/.venv/bin/activate
source /nfs/home/np04daq/bin/web_proxy.sh -u
cd "$root"
drunc-unified-shell ssh-CERN-kafka.json "$DAPHNE_CFG/sessions/pds-vst-session.data.xml" pds-m2-004 "$VST_SESSION"
