#!/usr/bin/env python3
"""Acquire all 32 channels at one common VGAIN per point, with guarded updates."""
import json,time,signal,hashlib
from pathlib import Path
from pds.core.runtime import DaphneBridge,RuntimeControl,MASK,APPLIED,PAUSE,PAUSED
from pds.calibration.timing import TimingSource
from acquisition_wire_ids import HDF5Acquisition
from ssp_routine import SSPRoutine
root=Path('/nfs/home/np04daq/vst/daphne-m2-004-offset2250-all32-20261016')
base=json.loads((root/'plans/offset2250-afe0-r3.json').read_text())
plan={'scan_id':'m2-004-joint-gain-offset2250-r4','run_number':45371,'gains':[500,1000,1500,2000,2500], 'afes':[0,1,2,3],'channels':list(range(32)),'offset':2250,'source_ids':[804,805,806,807], 'window_s':2,'clock_hz':62500000,'daq_trigger_hz':.5,'timing':base['timing'],'illumination':base['illumination'],'board_endpoint':base['board_endpoint'],'scope':'SSP commands and register readback on BOREAS; DAPHNE acquisition on GIB; no optical coupling'}
with (root/'plans/joint-gain-r4.json').open('x') as f:json.dump(plan,f,indent=2)
log=(root/'logs/joint-gain-r4.jsonl').open('x')
def event(name,**kw):
 row={'event':name,'unix_ns':time.time_ns(),**kw};log.write(json.dumps(row)+'\n');log.flush();print(json.dumps(row),flush=True)
def interrupted(*args):raise KeyboardInterrupt('Interrupted; stopping sources and pausing all AFEs')
signal.signal(signal.SIGTERM,interrupted)
b=DaphneBridge(plan['board_endpoint']);runtime=RuntimeControl(b);source=TimingSource(plan['timing'],90);ssp=SSPRoutine()
try:
 state=b.timing_status();assert state['endpoint_state']==8 and state['timestamp_valid'] and state['clocks_locked'] and state['endpoint_address']==22
 assert b.read32(0x94000020)==0xffffffff and b.read32(0x94000024)==0 and b.read32(0x94000028)&255==7
 assert b.read32(PAUSE)==0xffffffff
 event('plan',plan=plan,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),timing=state)
 with source.reserve():
  event('timing_preflight',status=source.preflight())
  acquisition=HDF5Acquisition(root/'data/calibration/raw',root/'data/calibration/joint-gain-r4',plan['source_ids'],60)
  event('acquisition_preflight',status=acquisition.preflight(plan))
  for step,gain in enumerate(plan['gains']):
   for afe in plan['afes']:runtime.pause_afe(afe)
   ready=[]
   for afe in plan['afes']:
    settings=[{'variable':'offset','target':ch,'value':2250,'gain':False} for ch in range(afe*8,afe*8+8)]+[{'variable':'vgain','target':afe,'value':gain}]
    ready.append(runtime.configure_afe(afe,settings,timing_channels=[],paused_channels=list(range(afe*8,afe*8+8)),settle_ms=100))
   assert b.read32(PAUSE)==0xffffffff
   optical=ssp(plan['illumination']['settings'])
   runtime._write_mask(MASK,APPLIED,0xffffffff)
   runtime._write_mask(PAUSE,PAUSED,0)
   event('point_configured',step_id=step,gain=gain,afes=ready,ssp=optical)
   before=b.counters(plan['channels'])
   started=source.start();event('point_started',step_id=step,gain=gain,timing=started)
   try:
    receipt=acquisition.collect({'scan_id':plan['scan_id'],'channels':plan['channels'],'window_s':2,'capture_tail_ms':20,'step_id':step,'settings':{'offset':2250,'vgain_all_afes':gain},'afes':plan['afes'],'ssp_configuration_verified':optical['verified']},started)
   finally:stopped=source.stop()
   time.sleep(.020)
   after=b.counters(plan['channels']);delta={ch:{k:after[ch][k]-before[ch][k] for k in before[ch]} for ch in before}
   for afe in plan['afes']:runtime.pause_afe(afe)
   assert stopped is not None and stopped['rejected']==0 and all(v['records']==stopped['sent'] and v['busy']==0 and v['full']==0 for v in delta.values()),'Capture loss on one or more channels'
   assert receipt['verified'] and set(receipt['received_counts'])==set(map(str,range(32)))
   event('point_complete',step_id=step,gain=gain,receipt=receipt,timing=stopped,counters=delta,ssp=ssp.telemetry())
 event('all_points_complete',gains=plan['gains'],channels=32)
except BaseException as error:
 event('scan_failed',error=str(error));raise
finally:
 cleanup={}
 try:cleanup['timing_stop']=source.stop()
 except Exception as e:cleanup['timing_error']=str(e)
 try:cleanup['ssp']=ssp.stop()
 except Exception as e:cleanup['ssp_error']=str(e)
 for afe in range(4):
  try:runtime.pause_afe(afe);cleanup[str(afe)]='paused'
  except Exception as e:cleanup[str(afe)]=str(e)
 event('final_cleanup',state=cleanup,timing=b.timing_status(),calibration_mask=b.read32(MASK),pause_mask=b.read32(PAUSE))
 b.close();log.close()

