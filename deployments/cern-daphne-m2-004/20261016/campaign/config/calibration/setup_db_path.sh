# Source after the DAQ workarea env.sh.
export DUNEDAQ_DB_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd):${DUNEDAQ_DB_PATH}"
