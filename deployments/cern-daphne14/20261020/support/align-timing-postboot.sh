set -eo pipefail
source /nfs/home/np04daq/vst/daphne-m2-004-offset2250-all32-20261016/runtime-env.sh
export PYTHONPATH="$PDS_PROTOBUF_DIR:$PDS_CHECKOUT/src${PYTHONPATH:+:$PYTHONPATH}"
"$PDS_VENV/bin/python" -u - <<'PY'
import json,time,uhal,timing.core
from pathlib import Path
from pds.core.runtime import DaphneBridge
from pds.calibration.timing import TimingSource
out=Path('/nfs/home/np04daq/vst/daphne14-pds-ta-charge-20261020/evidence/timing-alignment-postboot.json');assert not out.exists()
b=DaphneBridge('tcp://10.73.137.160:40001',timeout_ms=12000);report={}
source=TimingSource({'master':'GIB','connections':'/nfs/sw/dunedaq/timing/connections.xml','generator':1,'command_id':7,'rate_hz':1},15)
try:
 report['before']=b.timing_status();h=b.high
 if report['before']['endpoint_state']!=8 or report['before']['endpoint_address']!=32:
  try:
   response=b._call(h.MT2_CONFIGURE_CLKS_REQ,h.ConfigureCLKsRequest(id=32,ctrl_ep_clk=True,reset_MMCM1=True,reset_endpoint=True),h.ConfigureCLKsResponse);print('CLOCK_CONFIGURATION',response.message,flush=True)
  except RuntimeError as e:
   print('CLOCK_CONFIGURATION_RESPONSE',str(e),flush=True)
   report['clock_response']=str(e)
   if not b.timing_status()['clocks_locked']:raise
  time.sleep(2)
  with source.reserve():
   report['master_preflight']=source.preflight()
   uhal.setLogLevelTo(uhal.LogLevel.ERROR);d=uhal.ConnectionManager('file:///nfs/sw/dunedaq/timing/connections.xml').getDevice('GIB');d.setTimeoutPeriod(2000)
   d.getNode('').apply_endpoint_delay(32,0,0,0,False,True);time.sleep(1)
   state=b.timing_status();print('AFTER_STANDARD_ALIGN',state,flush=True)
   if state['endpoint_state']==6:d.getNode('master').transmit_async_packet([32,0,0xab,0xf0,0x81,0x103],-1)
 for i in range(10):
  state=b.timing_status();print('STATUS',state,flush=True)
  if state['endpoint_state']==8 and state['timestamp_valid'] and state['clocks_locked']:break
  time.sleep(.5)
 report['after']=state;out.write_text(json.dumps(report,indent=2)+'\n');assert state['endpoint_state']==8 and state['timestamp_valid'] and state['endpoint_address']==32
finally:b.close()
PY
