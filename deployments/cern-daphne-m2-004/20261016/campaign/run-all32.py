#!/usr/bin/env python3
"""Offset2250, four sender acquisition, sequential guarded AFE gain scans."""
import json,time,signal,hashlib
from pathlib import Path
from pds.core.runtime import DaphneBridge,RuntimeControl,MASK,PAUSE
from pds.calibration.timing import TimingSource
from pds.calibration.cli import run_scan
root=Path('/nfs/home/np04daq/vst/daphne-m2-004-offset2250-all32-20261016')
plans=[json.loads((root/f'plans/offset2250-afe{afe}.json').read_text()) for afe in range(4)]
log=(root/'logs/all32-orchestration.jsonl').open('x')
def event(name,**kw):
 row={'event':name,'unix_ns':time.time_ns(),**kw};log.write(json.dumps(row)+'\n');log.flush();print(json.dumps(row),flush=True)
def interrupted(*args):raise KeyboardInterrupt('Interrupted; pausing all AFEs')
signal.signal(signal.SIGTERM,interrupted)
b=DaphneBridge(plans[0]['board_endpoint']);runtime=RuntimeControl(b);source=TimingSource(plans[0]['timing'],15)
try:
 s=b.timing_status();assert s['endpoint_state']==8 and s['timestamp_valid'] and s['clocks_locked'] and s['endpoint_address']==22
 assert b.read32(0x94000020)==0xffffffff and b.read32(0x94000024)==0 and b.read32(0x94000028)&255==7
 assert b.read32(MASK)==0xffffffff and b.read32(PAUSE)==0xffffffff
 with source.reserve():
  event('timing_preflight',status=source.preflight())
  for afe in range(4):
   settings=plans[afe]['settings']+[{'variable':'vgain','target':afe,'value':2500}]
   ready=runtime.configure_afe(afe,settings,timing_channels=list(range(afe*8,afe*8+8)),paused_channels=[],settle_ms=100)
   event('afe_initialized',afe=afe,ready=ready)
  before=b.counters(list(range(32)))
  try:
   event('prime_started',timing=source.start());time.sleep(6)
  finally:stopped=source.stop()
  after=b.counters(list(range(32)));delta={ch:{k:after[ch][k]-before[ch][k] for k in before[ch]} for ch in before}
  event('prime_stopped',timing=stopped,counters=delta)
  assert stopped['rejected']==0 and all(v['records']==stopped['sent'] and v['busy']==0 and v['full']==0 for v in delta.values()),'Prime capture loss on one or more channels'
 for afe,plan in enumerate(plans):
  with source.reserve():
   source.preflight()
   # Other AFEs remain in timing-only CAL2 mode so all four DAQ senders have data.
   ready=runtime.configure_afe(afe,plan['settings'],timing_channels=[],paused_channels=[],settle_ms=100)
   event('afe_scan_prepared',afe=afe,ready=ready)
  run_scan(plan,root/'data/calibration/raw',root/f'data/calibration/afe{afe}-offset2250',root/f'logs/afe{afe}-offset2250.jsonl')
  event('afe_scan_complete',afe=afe)
  with source.reserve():
   source.preflight()
   runtime.configure_afe(afe,[],timing_channels=list(range(afe*8,afe*8+8)),paused_channels=[],settle_ms=100)
 event('all_scans_complete')
except BaseException as error:
 event('all32_failed',error=str(error));raise
finally:
 cleanup={}
 try:cleanup['timing_stop']=source.stop()
 except Exception as e:cleanup['timing_error']=str(e)
 for afe in range(4):
  try:runtime.pause_afe(afe);cleanup[str(afe)]='paused'
  except Exception as e:cleanup[str(afe)]=str(e)
 event('final_cleanup',state=cleanup,timing=b.timing_status(),calibration_mask=b.read32(MASK),pause_mask=b.read32(PAUSE))
 b.close();log.close()

