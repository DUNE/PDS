#!/usr/bin/env python3
"""Offset2250, four sender acquisition, sequential guarded AFE gain scans."""
import json,time,signal,hashlib
from pathlib import Path
from pds.core.runtime import DaphneBridge,RuntimeControl,MASK,PAUSE
from pds.calibration.timing import TimingSource
from pds.calibration.coordinator import Coordinator
from pds.calibration.journal import Journal
from acquisition_wire_ids import HDF5Acquisition
from ssp_routine import SSPRoutine

def run_scan(plan,input_dir,output_dir,journal_path):
 journal=Journal(journal_path);bridge=DaphneBridge(plan['board_endpoint']);timing=TimingSource(plan['timing'],plan['acquisition_timeout_s']+30)
 try:
  acquisition=HDF5Acquisition(input_dir,output_dir,plan['source_ids'],plan['acquisition_timeout_s'])
  Coordinator(RuntimeControl(bridge),timing,acquisition,journal,apply_optical=ssp).run(plan)
 finally:
  try:timing.stop()
  finally:bridge.close();journal.close()

root=Path('/nfs/home/np04daq/vst/daphne-m2-004-offset2250-all32-20261016')
all_plans=[json.loads((root/f'plans/offset2250-afe{afe}.json').read_text()) for afe in range(4)]
plans=[json.loads((root/f'plans/offset2250-afe{afe}-r3.json').read_text()) for afe in range(4)]
log=(root/'logs/all32-r3.jsonl').open('x')
ssp=SSPRoutine()
def event(name,**kw):
 row={'event':name,'unix_ns':time.time_ns(),**kw};log.write(json.dumps(row)+'\n');log.flush();print(json.dumps(row),flush=True)
def interrupted(*args):raise KeyboardInterrupt('Interrupted; pausing all AFEs')
signal.signal(signal.SIGTERM,interrupted)
b=DaphneBridge(plans[0]['board_endpoint']);runtime=RuntimeControl(b);source=TimingSource(plans[0]['timing'],90)
try:
 s=b.timing_status();assert s['endpoint_state']==8 and s['timestamp_valid'] and s['clocks_locked'] and s['endpoint_address']==22
 assert b.read32(0x94000020)==0xffffffff and b.read32(0x94000024)==0 and b.read32(0x94000028)&255==7
 assert b.read32(MASK)==0xffffffff and b.read32(PAUSE)==0xffffffff
 with source.reserve():
  event('timing_preflight',status=source.preflight())
  for afe in range(4):
   settings=all_plans[afe]['settings']+[{'variable':'vgain','target':afe,'value':2500}]
   ready=runtime.configure_afe(afe,settings,timing_channels=list(range(afe*8,afe*8+8)),paused_channels=[],settle_ms=100)
   event('afe_initialized',afe=afe,ready=ready)
  event('ssp_initial_configuration',acknowledgement=ssp(plans[0]['illumination']['settings']))
  before=b.counters(list(range(32)))
  try:
   event('prime_started',timing=source.start());time.sleep(6)
  finally:stopped=source.stop()
  after=b.counters(list(range(32)));delta={ch:{k:after[ch][k]-before[ch][k] for k in before[ch]} for ch in before}
  event('prime_stopped',timing=stopped,counters=delta)
  assert stopped['rejected']==0 and all(v['records']==stopped['sent'] and v['busy']==0 and v['full']==0 for v in delta.values()),'Prime capture loss on one or more channels'
 # Require a common verified window containing all32 channels across all four sources.
 with source.reserve():
  source.preflight()
  acquisition=HDF5Acquisition(root/'data/calibration/raw',root/'data/calibration/all32-data-taking-r3',[804,805,806,807],60)
  acquisition.preflight(dict(plans[0],clock_hz=62500000))
  before=b.counters(list(range(32)))
  started=source.start();event('all32_data_taking_started',timing=started)
  try:
   receipt=acquisition.collect({'scan_id':'m2-004-all32-data-taking-offset2250','channels':list(range(32)),'window_s':2,'capture_tail_ms':20,'step_id':0,'settings':{'offset':2250,'vgain_all_afes':2500}},started)
  finally:stopped=source.stop()
  time.sleep(.020)
  after=b.counters(list(range(32)));delta={ch:{k:after[ch][k]-before[ch][k] for k in before[ch]} for ch in before}
  assert stopped['rejected']==0 and all(v['records']==stopped['sent'] and v['busy']==0 and v['full']==0 for v in delta.values()),'Capture loss during all32 data-taking window'
  event('all32_data_taking_complete',receipt=receipt,timing=stopped,counters=delta,ssp=ssp.telemetry())
 for plan in plans:
  afe=plan['afe']
  with source.reserve():
   source.preflight()
   # Other AFEs remain in timing-only CAL2 mode so all four DAQ senders have data.
   ready=runtime.configure_afe(afe,plan['settings'],timing_channels=[],paused_channels=[],settle_ms=100)
   event('afe_scan_prepared',afe=afe,ready=ready)
  run_scan(plan,root/'data/calibration/raw',root/f'data/calibration/afe{afe}-offset2250-r3',root/f'logs/afe{afe}-offset2250-r3.jsonl')
  event('afe_scan_complete',afe=afe)
  with source.reserve():
   source.preflight()
   runtime.configure_afe(afe,[],timing_channels=list(range(afe*8,afe*8+8)),paused_channels=[],settle_ms=100)
 event('all_scans_complete')
except BaseException as error:
 event('all32_failed',error=str(error));raise
finally:
 cleanup={}
 try:cleanup['ssp']=ssp.stop()
 except Exception as e:cleanup['ssp_error']=str(e)
 try:cleanup['timing_stop']=source.stop()
 except Exception as e:cleanup['timing_error']=str(e)
 for afe in range(4):
  try:runtime.pause_afe(afe);cleanup[str(afe)]='paused'
  except Exception as e:cleanup[str(afe)]=str(e)
 event('final_cleanup',state=cleanup,timing=b.timing_status(),calibration_mask=b.read32(MASK),pause_mask=b.read32(PAUSE))
 b.close();log.close()

