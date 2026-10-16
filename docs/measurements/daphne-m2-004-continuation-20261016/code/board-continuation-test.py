#!/usr/bin/env python3
"""Pinned CAL2 only: pause/drain and acquire a bounded eight-channel self-trigger burst."""
import argparse,json,mmap,os,signal,time,hashlib
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--mode',choices=['inspect','prepare','burst'],default='inspect');p.add_argument('--continuation',type=int,choices=[0,1],default=0);p.add_argument('--duration',type=float,default=.5);p.add_argument('--output',required=True);a=p.parse_args()
assert 0<a.duration<=1
selected=[0,1,8,9,16,17,24,25];mask=sum(1<<x for x in selected);allmask=0xffffffff
fd=os.open('/dev/mem',os.O_RDWR|os.O_SYNC);pages={}
for base in [0x84000000,0x88000000,0x94000000,0xa0010000]:pages[base]=mmap.mmap(fd,4096,offset=base,prot=mmap.PROT_READ|mmap.PROT_WRITE)
def rd(addr):return int.from_bytes(pages[addr&~4095][addr&4095:(addr&4095)+4],'little')
def wr(addr,value):
 pages[addr&~4095][addr&4095:(addr&4095)+4]=value.to_bytes(4,'little')
 assert rd(addr)==value,('write mismatch',hex(addr))
def wait(addr,value):
 until=time.monotonic()+3
 while rd(addr)!=value:
  if time.monotonic()>until:raise TimeoutError(('acknowledgement',hex(addr),hex(rd(addr)),hex(value)))
  time.sleep(.001)
def pause():
 wr(0xa0010f0c,allmask);wait(0xa0010f10,allmask);wait(0xa0010f14,allmask)
def timing():return {'control':hex(rd(0x84000000)),'clock_status':hex(rd(0x84000004)),'endpoint':hex(rd(0x84000008)),'status':hex(rd(0x8400000c))}
def snapshot():
 result={}
 for ch in range(32):
  b=0xa0010000+32*ch;e=0xa0010800+32*ch;t=0xa0010500+16*ch
  def pair(addr):return rd(addr)|(rd(addr+4)<<32)
  result[str(ch)]={'records':pair(b+4),'busy':pair(b+12),'full':pair(b+20),'triggers':pair(t),'packets':pair(t+8),'continuations':pair(e),'continuation_drops':pair(e+8),'covered_triggers':pair(e+16),'descriptor_overflows':pair(e+24)}
 return result
def aborted(*args):raise KeyboardInterrupt('Aborted; pausing and draining')
for sig in [signal.SIGTERM,signal.SIGINT,signal.SIGHUP,signal.SIGALRM]:signal.signal(sig,aborted)
report={'mode':a.mode,'continuation':a.continuation,'channels':selected,'mask':hex(mask),'requested_duration_s':a.duration,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'before_timing':timing(),'initial_registers':{hex(x):hex(rd(x)) for x in [0x88000034,0x94000020,0x94000024,0x94000028,0x9400002c,0x94000030,0x94000034,0x9400003c,0x94000044,0xa0010f00,0xa0010f0c]},'initial_channel_registers':{str(ch):{'threshold':rd(0xa0010000+32*ch),'continuation':hex(rd(0xa001001c+32*ch))} for ch in range(32)}}
try:
 assert [rd(0x94000000+x) for x in [0xf0,0xf4,0xf8,0xfc]]==[0x44415048,0x20000,1,0x093e0579]
 assert rd(0xa0010f08)==0x43414c32
 if a.mode!='inspect':
  assert rd(0x84000000)&4 and rd(0x84000004)&3==3 and rd(0x8400000c)&31==24 and rd(0x84000008)&65535==22
  signal.alarm(10)
  pause()
  wr(0xa0010f00,0);wait(0xa0010f04,0)
  wr(0x94000020,mask);wr(0x94000024,0);wr(0x94000028,7);wr(0x94000030,0);wr(0x88000034,2)
  config=(a.continuation<<31)|(32<<16)|2
  for ch in selected:wr(0xa0010000+32*ch,1);wr(0xa001001c+32*ch,config)
  time.sleep(.01)
  report['configured']={'enabled':hex(rd(0x94000020)),'source_selector':rd(0x88000034),'calibration_mask':rd(0xa0010f00),'correlation_threshold':1,'continuation_config':hex(config),'activity_threshold_adc':2,'quiet_samples':32,'signal_delay_overlap':0}
  if a.mode=='burst':
   before=snapshot();begin=time.monotonic_ns();wr(0xa0010f0c,allmask^mask);wait(0xa0010f10,allmask^mask)
   try:time.sleep(a.duration)
   finally:pause()
   end=time.monotonic_ns();after=snapshot()
   delta={ch:{k:(after[ch][k]-before[ch][k])&0xffffffff for k in before[ch]} for ch in before}
   report.update(before_counters=before,after_counters=after,delta=delta,elapsed_unpause_through_drain_s=(end-begin)/1e9)
   assert all(delta[str(ch)]['records']==0 for ch in range(32) if ch not in selected),'Disabled channel produced records'
   report['all_selected_have_records']=all(delta[str(ch)]['records']>0 for ch in selected)
except BaseException as e:
 report['error']=str(e);raise
finally:
 if a.mode!='inspect':
  try:pause();report['cleanup']='all channels paused and drained'
  except BaseException as e:report['cleanup_error']=str(e)
  signal.alarm(0)
 report['final_timing']=timing();report['final_pause_mask']=hex(rd(0xa0010f0c))
 path=Path(a.output)
 with path.open('x') as f:json.dump(report,f,indent=2)
 print(json.dumps(report),flush=True)
 for mm in pages.values():mm.close()
 os.close(fd)
