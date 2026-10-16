#!/usr/bin/env python3
"""Read-only decoding of all-32 simultaneous gain scan, run45371."""
import hashlib,json,csv,platform,sys,subprocess,time
from pathlib import Path
import numpy as np
import fddetdataformats
root=Path('/nfs/home/np04daq/vst/daphne-m2-004-offset2250-all32-20261016')
out=root/'analysis-joint-gain-r4';out.mkdir(exist_ok=False)
journals=[root/'logs/joint-gain-r4.jsonl']
events=[json.loads(line) for journal in journals for line in journal.read_text().splitlines()]
assert sum(e['event']=='all_points_complete' for e in events)==1
cleanup=next(e for e in events if e['event']=='final_cleanup');assert cleanup['pause_mask']==0xffffffff and cleanup['state']['ssp']['led_registers_disabled']
steps=[e for e in events if e['event']=='point_complete'];assert len(steps)==5
assert [e['gain'] for e in steps]==[500,1000,1500,2000,2500]
report={'run':45371,'cleanup':cleanup,'verification_scope':'Complete gain-control and data-taking exercise; independent SSP timing master and no optical coupling to DAPHNE004','offset_dac':2250,'host':platform.node(),'python':sys.version,'numpy':np.__version__,'journal_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in journals},'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'metrics_definition':{'pedestal':'Arithmetic mean of all 256 raw unsigned ADC samples over all frames in channel.','rms_total':'Population standard deviation of all ADC samples in channel.','rms_within':'sqrt(mean of per-frame population variances)), excludes waveform-to-waveform DC drift.','rms_frame_median':'Median per-frame population standard deviation.','pedestal_drift':'Population standard deviation of per-frame means.','note':'No baseline subtraction, pulse rejection, or calibration applied.'},'steps':[]}
assert fddetdataformats.DAPHNEEthFrame.sizeof()==512
bits=np.arange(256)*14;wi=bits//16;sh=(bits%16).astype(np.uint32)
rows=[]
for e in steps:
 r=e['receipt'];point=r['settings']['vgain_all_afes'];p=Path(r['dataset']);data=p.read_bytes();sha=hashlib.sha256(data).hexdigest();assert sha==r['sha256'];assert len(data)%512==0
 raw=np.frombuffer(data,dtype=np.uint8).reshape(-1,512);n=len(raw)
 channels=raw[:,23].copy();ticks=raw[:,8:16].copy().view('<u8').reshape(-1)
 assert set(channels)==set(r['channels']);assert np.all(((raw[:,22]>>4)&15)==4)
 daq=raw[:,:8].copy().view('<u8').reshape(-1);wire_stream=((daq>>26)&255);assert np.all(wire_stream==64*(channels//16)+(channels%16)//8),'Unexpected wire stream ID'
 adc=np.empty((n,256),dtype=np.uint16)
 for start in range(0,n,2048):
  words=raw[start:start+2048,64:].copy().view('<u2').astype(np.uint32)
  words=np.pad(words,((0,0),(0,1)))
  adc[start:start+2048]=((words[:,wi]>>sh)|(words[:,wi+1]<<(16-sh)))&16383
 checks=np.unique(np.r_[np.linspace(0,n-1,33,dtype=int),[np.flatnonzero(channels==ch)[0] for ch in range(32)]])
 for index in checks:
  f=fddetdataformats.DAPHNEEthFrame(data[index*512:(index+1)*512]);expected=np.array([f.get_adc(i) for i in range(256)],dtype=np.uint16)
  assert np.array_equal(expected,adc[index]),('decoder mismatch',point,int(index))
 step={'offset_dac':2250,'vgain':point,'receipt':r,'input_sha256':sha,'official_decoder_crosscheck_frames':len(checks),'channels':[]}
 ready=next(x for x in events if x['event']=='point_configured' and x['step_id']==e['step_id'])
 for afe in range(4):
  settings=ready['afes'][afe]['settings']
  assert len(settings)==9 and all(t['value']==2250 for t in settings if t['variable']=='offset')
  assert [t['value'] for t in settings if t['variable']=='vgain']==[point]
 assert ready['ssp']['verified']
 step['point_ready']=ready
 assert e['timing']['rejected']==0 and all(c['records']==e['timing']['sent'] and c['busy']==0 and c['full']==0 for c in e['counters'].values())
 reference=None
 for ch in r['channels']:
  mask=channels==ch;a=adc[mask].astype(np.float64);ct=ticks[mask];assert len(a)==r['received_counts'][str(ch)];assert np.all(np.diff(np.sort(ct))==10752)
  ordered=np.sort(ct)
  if reference is not None:assert np.array_equal(ordered,reference)
  reference=ordered
  means=a.mean(axis=1);variances=a.var(axis=1);rms=np.sqrt(variances)
  stats={'firmware_afe':ch//8,'board_afe':[0,4,3,2][ch//8],'offset_dac':2250,'vgain':point,'channel':ch,'frames':len(a),'samples':a.size,'pedestal':float(a.mean()),'rms_total':float(a.std()),'rms_within':float(np.sqrt(variances.mean())),'rms_frame_median':float(np.median(rms)),'pedestal_drift':float(means.std()),'pedestal_frame_median':float(np.median(means)),'rms_frame_p05':float(np.quantile(rms,.05)),'rms_frame_p95':float(np.quantile(rms,.95)),'min':int(a.min()),'max':int(a.max()),'fraction_zero':float((a==0).mean()),'fraction_fullscale':float((a==16383).mean()),'pedestal_first64':float(a[:,:64].mean()),'rms_first64':float(np.sqrt(a[:,:64].var(axis=1).mean())),'q01':float(np.quantile(a,.01)),'q50':float(np.quantile(a,.5)),'q99':float(np.quantile(a,.99))}
  rows.append(stats);step['channels'].append(dict(stats,mean_waveform=a.mean(axis=0).tolist(),rms_by_sample=a.std(axis=0).tolist(),example_waveform=a[0].astype(int).tolist()))
 report['steps'].append(step)
 print('DECODED',point,'frames',n,'sha256 verified; official decoder crosscheck passed',flush=True)
with (out/'channel-statistics.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
report['runtime_source']={}
for repo in ['/nfs/home/np04daq/calib/control/PDS','/nfs/home/marroyav/workareas/daq/daphne/pds-trigger-dev-20260930/sourcecode/fddetdataformats']:
 report['runtime_source'][repo]={'commit':subprocess.check_output(['git','-c','safe.directory='+repo,'-C',repo,'rev-parse','HEAD'],text=True).strip(),'status':subprocess.check_output(['git','-c','safe.directory='+repo,'-C',repo,'status','--porcelain'],text=True)}
(out/'analysis.json').write_text(json.dumps(report,indent=2)+'\n')
print('ANALYSIS_COMPLETE',str(out),flush=True)
for gain in [500,1000,1500,2000,2500]:
 group=[r for r in rows if r['vgain']==gain]
 print('GAIN_SUMMARY',json.dumps({'gain':gain,'channels':len(group),'pedestal_range':[min(r['pedestal'] for r in group),max(r['pedestal'] for r in group)],'within_rms_range':[min(r['rms_within'] for r in group),max(r['rms_within'] for r in group)],'zero_clip_max':max(r['fraction_zero'] for r in group),'fullscale_clip_max':max(r['fraction_fullscale'] for r in group)}),flush=True)

