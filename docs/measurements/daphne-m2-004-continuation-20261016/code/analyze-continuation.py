#!/usr/bin/env python3
"""Read-only audit of sparse self-trigger/continuation DAQ windows."""
import argparse,hashlib,json,csv,collections,platform,sys,struct
from pathlib import Path
import numpy as np
import hdf5libs,daqdataformats,fddetdataformats
p=argparse.ArgumentParser();p.add_argument('--run',type=int,required=True);p.add_argument('--label',required=True);p.add_argument('--continuation',type=int,choices=[0,1],required=True);p.add_argument('--max-windows',type=int,default=3);a=p.parse_args()
r=Path('/nfs/home/np04daq/vst/daphne-m2-004-continuation-2ch-20261016');out=r/'data/selected'/a.label;out.mkdir(exist_ok=False)
channels=[0,1,8,9,16,17,24,25];sources={804:[0,1],805:[8,9],806:[16,17],807:[24,25]};records=[];rejected=[];rows=[]
bits=np.arange(256)*14;wi=bits//16;sh=(bits%16).astype(np.uint32)
files=sorted((r/'data/calibration/raw').glob(f'*run{a.run:06d}_*.hdf5'))
for path in files:
 rawfile=hdf5libs.HDF5RawDataFile(str(path))
 for record in rawfile.get_all_record_ids():
  frags={}
  for fp in rawfile.get_fragment_dataset_paths(record):
   f=rawfile.get_frag(fp);h=f.get_header()
   if h.fragment_type==daqdataformats.FragmentType.kDAPHNEEth.value and h.element_id.id in sources:frags[h.element_id.id]=f
  if set(frags)!=set(sources):rejected.append({'file':str(path),'record':str(record),'reason':'missing source'});continue
  widths={(f.get_header().window_begin,f.get_header().window_end) for f in frags.values()}
  assert len(widths)==1
  begin,end=next(iter(widths));assert end-begin==312500
  flags={str(s):int(f.get_header().status_bits) for s,f in frags.items()}
  payloads={s:f.get_data_bytes() for s,f in frags.items()}
  if any(flags.values()) or any(not x for x in payloads.values()):
   rejected.append({'file':str(path),'record':str(record),'reason':'status or empty','status':flags,'bytes':{str(s):len(x) for s,x in payloads.items()}});continue
  payload=b''.join(payloads[s] for s in sorted(sources));assert len(payload)%512==0
  x=np.frombuffer(payload,dtype=np.uint8).reshape(-1,512);n=len(x)
  ch=x[:,23].copy();ticks=x[:,8:16].copy().view('<u8').reshape(-1)
  daq=x[:,:8].copy().view('<u8').reshape(-1);header=x[:,16:24].copy().view('<u8').reshape(-1)
  assert set(ch)==set(channels),'unexpected active channels'
  assert np.all(((header>>52)&15)==4) and np.all(((daq>>52)&4095)==63)
  assert np.all(((daq>>26)&255)==64*(ch//16)+(ch%16)//8)
  assert np.all(((header>>46)&3)==0),'non-self-trigger calibration tag observed'
  assert np.all((ticks>=begin)&(ticks<end))
  for s,data in payloads.items():assert set(np.frombuffer(data,dtype=np.uint8).reshape(-1,512)[:,23])==set(sources[s])
  counts={str(c):int((ch==c).sum()) for c in channels}
  if min(counts.values())<16:rejected.append({'file':str(path),'record':str(record),'reason':'too few frames','counts':counts});continue
  adc=np.empty((n,256),dtype=np.uint16)
  for i in range(0,n,2048):
   w=x[i:i+2048,64:].copy().view('<u2').astype(np.uint32);w=np.pad(w,((0,0),(0,1)))
   adc[i:i+2048]=((w[:,wi]>>sh)|(w[:,wi+1]<<(16-sh)))&16383
  checks=np.unique(np.r_[np.linspace(0,n-1,17,dtype=int),[np.flatnonzero(ch==c)[0] for c in channels]])
  for i in checks:
   f=fddetdataformats.DAPHNEEthFrame(payload[i*512:(i+1)*512])
   assert np.array_equal(adc[i],[f.get_adc(k) for k in range(256)])
  index=len(records);binpath=out/f'window-{index:03d}.bin'
  with binpath.open('xb') as f:f.write(payload)
  stats=[];examples={}
  for c in channels:
   ii=np.flatnonzero(ch==c);ii=ii[np.argsort(ticks[ii],kind='stable')];ts=ticks[ii];h=header[ii];v=adc[ii]
   delta=np.diff(ts).astype(np.int64);assert np.all(delta>0),'Duplicate/nonmonotonic timestamp within readout window'
   cont=((h>>51)&1).astype(bool);overflow=((h>>49)&1).astype(bool)
   if not a.continuation:assert not cont.any(),'Continuation flag set in disabled reference'
   linked=cont[1:];adjacent=delta==256
   # A gap is an observation to compare with hardware drop counters, not hidden.
   stat={'label':a.label,'run':a.run,'window':index,'channel':c,'frames':len(ii),'continuation_frames':int(cont.sum()),'descriptor_overflow_frames':int(overflow.sum()),'dt256_pairs':int(adjacent.sum()),'dt_lt256_pairs':int((delta<256).sum()),'continuation_pairs':int(linked.sum()),'continuation_pairs_dt256':int((linked&adjacent).sum()),'continuation_pairs_with_gap':int((linked&~adjacent).sum()),'min_dt_ticks':int(delta.min()),'max_dt_ticks':int(delta.max()),'pedestal':float(v.mean()),'rms_total':float(v.std()),'rms_within':float(np.sqrt(v.astype(float).var(axis=1).mean())),'fraction_zero':float((v==0).mean()),'fraction_fullscale':float((v==16383).mean()),'timestamp_first':int(ts[0]),'timestamp_last':int(ts[-1]),'most_common_dt_ticks':collections.Counter(map(int,delta)).most_common(8)}
   stats.append(stat);rows.append(stat)
   # Retain a short consecutive-frame trace (prefer a continuation chain).
   first=0
   if cont.any():first=max(0,int(np.flatnonzero(cont)[0])-1)
   examples[str(c)]={'timestamps':ts[first:first+12].astype(object).tolist(),'continuation':cont[first:first+12].astype(int).tolist(),'adc':v[first:first+12].astype(int).tolist()}
  receipt={'run':a.run,'label':a.label,'continuation_enabled':bool(a.continuation),'file':str(path),'hdf5_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'record_id':str(record),'window_begin':begin,'window_end':end,'source_ids':sorted(frags),'fragment_status':flags,'frame_bytes':512,'samples_per_frame':256,'received_counts':counts,'dataset':str(binpath),'sha256':hashlib.sha256(payload).hexdigest(),'official_decoder_crosscheck_frames':len(checks),'channels':stats,'examples':examples}
  (binpath.with_suffix('.json')).write_text(json.dumps(receipt,indent=2)+'\n');records.append(receipt)
  print('AUDITED',a.label,'window',index,'frames',n,'continuations',sum(s['continuation_frames'] for s in stats),flush=True)
  if len(records)>=a.max_windows:break
 if len(records)>=a.max_windows:break
report={'run':a.run,'label':a.label,'host':platform.node(),'python':sys.version,'numpy':np.__version__,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'closed_hdf5_files_found':len(files),'selected_windows':len(records),'records':records,'rejected_records':rejected,'scope':'Self-trigger/continuation characterization; selected 5ms windows, not entire burst; no shared-event alignment requirement across independent channels'}
(out/'analysis.json').write_text(json.dumps(report,indent=2)+'\n')
if rows:
 with (out/'channel-statistics.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print('RESULT',json.dumps({'run':a.run,'label':a.label,'windows':len(records),'frames':sum(s['frames'] for s in rows),'continuations':sum(s['continuation_frames'] for s in rows),'cont_pairs_dt256':sum(s['continuation_pairs_dt256'] for s in rows),'cont_pairs_gaps':sum(s['continuation_pairs_with_gap'] for s in rows),'rejected_records':len(rejected)}),flush=True)
if not records:raise SystemExit('No complete four-source window with all eight selected channels was found')

