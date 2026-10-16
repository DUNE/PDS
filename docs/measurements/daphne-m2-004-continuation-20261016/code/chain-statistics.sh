set -eo pipefail
root=/nfs/home/np04daq/vst/daphne-m2-004-continuation-2ch-20261016
source "$root/runtime-env.sh"
export PYTHONPATH="$root:$PDS_PROTOBUF_DIR:$PDS_CHECKOUT/src${PYTHONPATH:+:$PYTHONPATH}"
"$PDS_VENV/bin/python" - <<'PY'
from pathlib import Path
import json,hashlib,collections
import numpy as np
r=Path('/nfs/home/np04daq/vst/daphne-m2-004-continuation-2ch-20261016');result={}
for label in ['continuation-off-r2','continuation-on-r2']:
 report=json.loads((r/'data/selected'/label/'analysis.json').read_text());rows=[]
 for record in report['records']:
  p=Path(record['dataset']);data=p.read_bytes();assert hashlib.sha256(data).hexdigest()==record['sha256']
  raw=np.frombuffer(data,dtype=np.uint8).reshape(-1,512);ch=raw[:,23];tick=raw[:,8:16].copy().view('<u8').reshape(-1);header=raw[:,16:24].copy().view('<u8').reshape(-1)
  for c in record['channels']:
   channel=c['channel'];ii=np.flatnonzero(ch==channel);ii=ii[np.argsort(tick[ii],kind='stable')];ts=tick[ii];cont=((header[ii]>>51)&1).astype(bool);run=1;lengths=[]
   for j in range(1,len(ii)):
    if cont[j] and ts[j]-ts[j-1]==256:run+=1
    else:lengths.append(run);run=1
   lengths.append(run)
   rows.append({'window':p.name,'channel':channel,'longest_observed_chain_frames':max(lengths),'longest_observed_chain_us':max(lengths)*256/62.5,'observed_runs':len(lengths),'chain_length_histogram':dict(collections.Counter(lengths)),'first_frame_continuation':bool(cont[0]),'last_frame_continuation':bool(cont[-1])})
 result[label]={'run':report['run'],'rows':rows,'scope':'Observed linked runs inside selected 5ms windows; boundary runs may be truncated.'}
with (r/'logs/chain-statistics-r2.json').open('x') as f:json.dump(result,f,indent=2)
print(json.dumps({k:max(x['longest_observed_chain_frames'] for x in v['rows']) for k,v in result.items()}))
PY
