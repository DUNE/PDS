#!/bin/bash
set -e
root=/nfs/home/np04daq/vst/daphne14-pds-ta-charge-20261020
source /nfs/home/np04daq/vst/daphne-m2-004-offset2250-all32-20261016/runtime-env.sh
export DUNE_DAQ_BASE_RELEASE=fddaq-v5.6.2-a9-1
export SPACK_RELEASES_DIR=/cvmfs/dunedaq.opensciencegrid.org/spack/releases
export DUNEDAQ_DB_PATH="$root/config:$DUNEDAQ_DB_PATH"
source /cvmfs/dunedaq.opensciencegrid.org/spack/releases/fddaq-v5.6.2-a9-1/.venv/bin/activate
source /nfs/home/np04daq/bin/web_proxy.sh -u
cd "$root"
drunc-unified-shell ssh-CERN-kafka.json "$root/config/sessions/pds-vst-session.data.xml" pds-daphne14 pds-vst-daphne14-pds-ta-charge
