set -eo pipefail
root=/nfs/home/np04daq/vst/daphne-m2-004-continuation-2ch-20261016
source "$root/runtime-env.sh"
export PYTHONPATH="$root:$PDS_PROTOBUF_DIR:$PDS_CHECKOUT/src${PYTHONPATH:+:$PYTHONPATH}"
"$PDS_VENV/bin/python" - <<'PY'
import json
from pathlib import Path
from pds.core.runtime import DaphneBridge,RuntimeControl
b=DaphneBridge('tcp://10.73.137.113:40001');r=RuntimeControl(b);report=[]
try:
 assert b.read32(0xa0010f0c)==0xffffffff and b.read32(0x94000020)==0x03030303
 for afe in range(4):
  settings=[{'variable':'offset','target':ch,'value':2250,'gain':False} for ch in range(afe*8,afe*8+8)]+[{'variable':'vgain','target':afe,'value':2500}]
  report.append(r.configure_afe(afe,settings,timing_channels=[],paused_channels=list(range(afe*8,afe*8+8)),settle_ms=100))
 print(json.dumps(report))
 Path('/nfs/home/np04daq/vst/daphne-m2-004-continuation-2ch-20261016/logs/analog-prepared-r2.json').write_text(json.dumps(report,indent=2)+'\n')
finally:b.close()
PY
