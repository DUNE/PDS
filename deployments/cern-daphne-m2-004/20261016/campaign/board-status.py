#!/usr/bin/env python3
"""Live CAL2/timing status; build identity is pinned by the verified deployment."""
import argparse,json,sys
from pathlib import Path
from pds.core.runtime import DaphneBridge
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--require-ready',action='store_true');p.add_argument('--require-timing',action='store_true');a=p.parse_args()
site=json.loads((Path(__file__).resolve().parent/'site.json').read_text())
b=DaphneBridge('tcp://'+site['control_host']+':40001',timeout_ms=3000)
try:
 timing=b.timing_status()
 regs={name:b.read32(address) for name,address in [('cal2',0xA0010F08),('selector',0x88000034),('enabled',0x94000020),('software_enabled',0x94000024),('command_id',0x94000028),('calibration_mask',0xA0010F00),('pause_mask',0xA0010F0C)]}
 print(json.dumps({'board':site['device'],'timing':timing,'registers':{k:hex(v) for k,v in regs.items()},'deployment_build':site['firmware']['observed_build'],'identity_provenance':'Board daphne-gateware live identity verification at deployment; register RPC does not expose identity addresses'},indent=2))
 if a.require_ready or a.require_timing:
  assert site['firmware']['verified'] and site['firmware']['observed_build']=='0x093e0579','Pinned deployment must be verified'
  assert regs['cal2']==0x43414c32,'CAL2 capability missing'
  assert timing['endpoint_address']==0x16 and timing['clock_source']=='endpoint' and timing['clocks_locked'],'Endpoint clock/address mismatch'
  assert timing['endpoint_state']==8 and timing['timestamp_valid'],'Aligned endpoint and valid timestamps required'
 if a.require_ready:
  assert regs['selector']==2 and regs['enabled']&255==255,'AFE0 digital preparation required'
  assert regs['software_enabled']&255==0 and regs['command_id']&255==7,'Timing-only command 7 required'
  assert regs['calibration_mask']&255==0 and regs['pause_mask']&255==0,'Reconcile AFE0 calibration/pause state'
except (RuntimeError,TimeoutError,OSError,AssertionError) as e:print(str(e),file=sys.stderr);sys.exit(1)
finally:b.close()
