#!/usr/bin/env python3
import pathlib,hashlib,json,collections,struct,platform,sys
import hdf5libs,daqdataformats as q,fddetdataformats as fd,trgdataformats as t
r=pathlib.Path('/nfs/home/np04daq/vst/daphne14-pds-ta-charge-20261020');sources={800:range(0,8),801:range(8,16),802:range(16,24),803:range(24,32)}
files=sorted((r/'data/calibration/raw').glob('*run045392_*.hdf5'));report={'run':45392,'host':platform.node(),'python':sys.version,'files':{},'records':[]};channels=collections.Counter();types=collections.Counter();status=collections.Counter();totalframes=0

def stream(cls,payload):
 pos=0
 while pos<len(payload):
  o=cls(payload[pos:]);n=o.sizeof();assert 0<n<=len(payload)-pos,(cls,n,len(payload)-pos)
  yield o;pos+=n
 assert pos==len(payload)
for path in files:
 report['files'][str(path)]={'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'bytes':path.stat().st_size};f=hdf5libs.HDF5RawDataFile(str(path))
 for rec in f.get_all_record_ids():
  frags={};tas=[];tcs=[];counts=collections.Counter();row={'file':str(path),'record':list(rec),'fragments':[]}
  for d in f.get_fragment_dataset_paths(rec):
   x=f.get_frag(d);h=x.get_header();b=x.get_data_bytes();sid=h.element_id.id;kind=h.fragment_type
   row['fragments'].append({'source':sid,'type':kind,'detector':h.detector_id,'bytes':len(b),'status':h.status_bits,'begin':h.window_begin,'end':h.window_end});status[str(h.status_bits)]+=1
   if sid in sources:
    assert kind==q.FragmentType.kDAPHNEEth.value and h.detector_id==8
    assert len(b)>0 and len(b)%512==0
    got=set()
    for off in range(0,len(b),512):
     raw=b[off:off+512];c=raw[23];stamp=struct.unpack_from('<Q',raw,8)[0];wire=(struct.unpack_from('<Q',raw,0)[0]>>26)&255
     assert c in sources[sid] and wire==64*(c//16)+(c%16)//8,(sid,c,wire)
     assert h.window_begin<=stamp<h.window_end
     assert raw[22]>>4==4
     frame=fd.DAPHNEEthFrame(raw);adcs=[frame.get_adc(i) for i in range(256)];assert all(0<=v<16384 for v in adcs)
     counts[c]+=1;got.add(c);totalframes+=1
    assert got==set(sources[sid]),(sid,got)
    frags[sid]=(h.window_begin,h.window_end)
   elif sid==900:
    assert kind==q.FragmentType.kWIBEth.value and h.detector_id==10 and len(b)>0
    assert len(b)%fd.WIBEthFrame.sizeof()==0
    stamps=[fd.WIBEthFrame(b[i:i+fd.WIBEthFrame.sizeof()]).get_timestamp() for i in range(0,len(b),fd.WIBEthFrame.sizeof())]
    assert all(y-x==2048 for x,y in zip(stamps,stamps[1:]))
    assert stamps[0]<=h.window_begin and stamps[-1]+2048>=h.window_end
    row['charge_first_timestamp']=stamps[0];row['charge_last_timestamp']=stamps[-1];row['charge_frames']=len(stamps)
    frags[sid]=(h.window_begin,h.window_end)
   elif kind==q.FragmentType.kTriggerActivity.value:
    for ta in stream(t.TriggerActivity,b):
     a=ta.data;assert a.type==t.TriggerActivityData.Type.kPDS and a.detid==8
     assert a.time_start<=a.time_activity<=a.time_end and a.time_end-a.time_start<=256
     n=ta.n_inputs() if callable(ta.n_inputs) else ta.n_inputs
     assert n>=1
     tas.append({'start':a.time_start,'end':a.time_end,'activity':a.time_activity,'type':str(a.type),'algorithm':str(a.algorithm),'detid':a.detid,'inputs':n})
   elif kind==q.FragmentType.kTriggerCandidate.value:
    for tc in stream(t.TriggerCandidate,b):
     a=tc.data;assert a.type==t.TriggerCandidateData.Type.kPrescale and a.detid==8
     tcs.append({'start':a.time_start,'end':a.time_end,'candidate':a.time_candidate,'type':str(a.type),'algorithm':str(a.algorithm),'detid':a.detid})
  assert set(frags)==set(sources)|{900},set(frags)
  assert len(set(frags.values()))==1,frags
  begin,end=next(iter(frags.values()));assert end-begin==62500
  assert all(x['status']==0 for x in row['fragments'] if x['source'] in set(sources)|{900}),row
  row['metadata_status']={str(x['source']):x['status'] for x in row['fragments'] if x['source'] not in set(sources)|{900}}
  assert set(counts)==set(range(32));channels.update(counts)
  assert tas and tcs
  assert all(any(tc['candidate']==ta['activity'] for ta in tas) for tc in tcs)
  assert all(begin==tc['candidate']-31250 and end==tc['candidate']+31250 for tc in tcs)
  row.update(frames=sum(counts.values()),channels=dict(counts),tas=tas,tcs=tcs);report['records'].append(row)
report.update(record_count=len(report['records']),pds_frames=totalframes,channel_frames=dict(channels),fragment_status_counts=dict(status),window_ticks=62500,window_ms=1.0,all_records_have_all32_channels=True,all_records_have_charge=True,all_tas_are_pds=True,all_tcs_are_prescale=True,script_sha256=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest())
report['fully_zero_status_records']=sum(all(x['status']==0 for x in row['fragments']) for row in report['records'])
report['metadata_flagged_records']=[row['record'] for row in report['records'] if any(row['metadata_status'].values())]
assert report['record_count']>0
(r/'evidence/decoded-run45392.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ['files','records']},indent=2),flush=True)
