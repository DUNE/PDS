from pathlib import Path
import json,hashlib
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
r=Path('/home/arroyave/work/daphne-m2-004-continuation-2ch-20261016');ev=r/'operator-evidence';out=r/'analysis-comparison';out.mkdir(exist_ok=True)
reports={k:json.loads((ev/'data/selected'/k/'analysis.json').read_text()) for k in ['continuation-off-r2','continuation-on-r2']}
long_examples=json.loads((ev/'logs/long-chain-examples-r2.json').read_text())
fig,axes=plt.subplots(4,2,figsize=(12,9),sharex=True,sharey='row',constrained_layout=True)
for col,(label,report) in enumerate(reports.items()):
 for row,ch in enumerate([0,8,16,24]):
  ex=report['records'][0]['examples'][str(ch)] if col==0 else long_examples[str(ch)];ts=np.array(ex['timestamps'],dtype=np.uint64);adc=np.array(ex['adc']);base=adc.mean()
  for i in range(len(ts)):
   x=((int(ts[i])-int(ts[0]))+np.arange(256))/62.5
   axes[row,col].plot(x,adc[i]-base,lw=.65,color=plt.cm.tab10(i%10))
   axes[row,col].axvline((int(ts[i])-int(ts[0]))/62.5,color='0.75',lw=.5,ls=':')
  axes[row,col].set_ylabel(f'Channel {ch}\nADC - trace mean')
  axes[row,col].set_xlim(0,55);axes[row,col].grid(alpha=.15)
  if row==0:axes[row,col].set_title(f'Continuation {"OFF" if col==0 else "ON"} · run {report["run"]}')
  if row==3:axes[row,col].set_xlabel('Time from first displayed sample (µs)')
fig.suptitle('DAPHNE-M2-004 · two channels per sender · noise-driven self-trigger\nCorrelation code 1; residual threshold 2 ADC; quiet limit 32; offset 2250; VGAIN 2500\nOne channel per sender; ON shows a long-chain excerpt; colors mark 256-sample frames',fontsize=11)
fig.savefig(out/'continuation-waveforms.png',dpi=170,bbox_inches='tight',pad_inches=.15);fig.savefig(out/'continuation-waveforms.pdf',bbox_inches='tight',pad_inches=.15)
