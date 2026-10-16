set -eo pipefail
root=/nfs/home/np04daq/vst/daphne-m2-004-continuation-2ch-20261016
source "$root/runtime-env.sh"
"$PDS_VENV/bin/python" - <<'PY'
from pathlib import Path
import json,hashlib
import numpy as np
r=Path('/nfs/home/np04daq/vst/daphne-m2-004-continuation-2ch-20261016');report=json.loads((r/'data/selected/continuation-on-r2/analysis.json').read_text());best={}
bits=np.arange(256)*14;wi=bits//16;sh=(bits%16).astype(np.uint32)
for rec in report['records']:
 data=Path(rec['dataset']).read_bytes();assert hashlib.sha256(data).hexdigest()==rec['sha256'];raw=np.frombuffer(data,dtype=np.uint8).reshape(-1,512)
 ch=raw[:,23];ticks=raw[:,8:16].copy().view('<u8').reshape(-1);head=raw[:,16:24].copy().view('<u8').reshape(-1)
 for c in rec['channels']:
  channel=c['channel'];ii=np.flatnonzero(ch==channel);ii=ii[np.argsort(ticks[ii])];ts=ticks[ii];cont=((head[ii]>>51)&1).astype(bool);start=0;longest=(0,1)
  for j in range(1,len(ii)+1):
   if j==len(ii) or not (cont[j] and ts[j]-ts[j-1]==256):
    if j-start>longest[1]:longest=(start,j-start)
    start=j
  begin,length=longest
  if str(channel) in best and best[str(channel)]['chain_frames']>=length:continue
  take=ii[begin:begin+min(length,12)];w=raw[take,64:].copy().view('<u2').astype(np.uint32);w=np.pad(w,((0,0),(0,1)));adc=((w[:,wi]>>sh)|(w[:,wi+1]<<(16-sh)))&16383
  best[str(channel)]={'run':45374,'dataset':rec['dataset'],'source_sha256':rec['sha256'],'chain_frames':length,'timestamps':ticks[take].astype(object).tolist(),'continuation':((head[take]>>51)&1).astype(int).tolist(),'adc':adc.astype(int).tolist(),'scope':'First up-to12 frames of longest observed linked run in the3 selected5ms windows; boundary truncation possible.'}
with (r/'logs/long-chain-examples-r2.json').open('x') as f:json.dump(best,f,indent=2)
print({c:x['chain_frames'] for c,x in best.items()})
PY
