#!/usr/bin/env python3
"""Bounded CAL2 software captures; keep self-trigger and timing injection disabled."""
import mmap,os,struct,time,signal,json,sys,pathlib,hashlib
mode=sys.argv[1];assert mode in ['prepare','burst','inspect'];report={'mode':mode,'script_sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()}
fd=os.open('/dev/mem',os.O_RDWR|os.O_SYNC);maps={b:mmap.mmap(fd,4096,offset=b) for b in [0x84000000,0x88000000,0x94000000,0xa0010000]}
def rd(a):return struct.unpack_from('<I',maps[a&~4095],a&4095)[0]
def wr(a,v,check=True):
 struct.pack_into('<I',maps[a&~4095],a&4095,v)
 if check:assert rd(a)==v,(hex(a),hex(rd(a)),hex(v))
def wait(a,v):
 end=time.monotonic()+3
 while rd(a)!=v:
  if time.monotonic()>end:raise TimeoutError(hex(a))
  time.sleep(.001)
def pause(idle=True):
 wr(0xa0010f0c,0xffffffff);wait(0xa0010f10,0xffffffff)
 if idle:wait(0xa0010f14,0xffffffff)
def snap():
 def pair(a):return rd(a)|(rd(a+4)<<32)
 return {str(c):{'records':pair(0xa0010004+32*c),'busy':pair(0xa001000c+32*c),'full':pair(0xa0010014+32*c)} for c in range(32)}
def abort(*args):raise KeyboardInterrupt('bounded producer interrupted')
for sig in [signal.SIGTERM,signal.SIGINT,signal.SIGHUP,signal.SIGALRM]:signal.signal(sig,abort)
try:
 assert [rd(0x940000f0+i) for i in [0,4,8,12]]==[0x44415048,0x20000,1,0x093e0579]
 assert rd(0x84000004)&3==3 and rd(0x8400000c)&31==24 and rd(0x84000008)&65535==32
 if mode!='inspect':
  signal.alarm(25);pause(False);wr(0xa0010f00,0);wait(0xa0010f04,0)
  wr(0x94000020,0xffffffff);wr(0x94000024,0);wr(0x94000028,7);wr(0x88000034,0)
  for c in range(32):wr(0xa001001c+32*c,(32<<16)|2)
  report['enabled_channels']=list(range(32));report['descriptor_config']='0x00200002';report['source_selector']=rd(0x88000034)
 if mode=='burst':
  wait(0xa0010f14,0xffffffff);before=snap();start=time.monotonic();wr(0xa0010f0c,0);wait(0xa0010f10,0)
  count=200;rate=20
  for n in range(count):
   delay=start+n/rate-time.monotonic()
   if delay>0:time.sleep(delay)
   wr(0x88000008,0xbaba,False)
  pause();after=snap();report.update(writes=count,rate_hz=rate,elapsed_s=time.monotonic()-start,before=before,after=after,delta={c:{k:after[c][k]-before[c][k] for k in before[c]} for c in before})
 else:report['counters']=snap()
finally:
 if mode!='inspect':
  try:pause(mode=='burst');report['final_pause_mask']=hex(rd(0xa0010f0c))
  except Exception as e:report['cleanup_error']=str(e)
  signal.alarm(0)
 print(json.dumps(report),flush=True)
 for m in maps.values():m.close()
 os.close(fd)
