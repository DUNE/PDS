set -eo pipefail
root=/nfs/home/np04daq/vst/daphne-m2-004-pds-ta-charge-20261020
cp /tmp/pds-prescale-CMakeLists-20261020.txt "$root/prescale-compat/CMakeLists.txt"
source /nfs/home/np04daq/vst/daphne-m2-004-offset2250-all32-20261016/runtime-env.sh
export CMAKE_PREFIX_PATH="$(python3 - <<'PY'
import os
from pathlib import Path
print(':'.join(str(Path(p).parent) for p in (os.environ['LD_LIBRARY_PATH']+':'+os.environ['DUNEDAQ_DB_PATH']).split(':') if p))
PY
)${CMAKE_PREFIX_PATH:+:$CMAKE_PREFIX_PATH}"
json_dir=$(sed -n 's/^nlohmann_json_DIR:PATH=//p' /nfs/home/marroyav/workareas/daq/daphne/pds-trigger-dev-20260930/build/CMakeCache.txt)
cmake -Dnlohmann_json_DIR="$json_dir" -S "$root/prescale-compat" -B "$root/prescale-compat/build-r2" -DPYBIND11_FINDPYTHON=ON
cmake --build "$root/prescale-compat/build-r2" -j 2
ctest --test-dir "$root/prescale-compat/build-r2" --output-on-failure
