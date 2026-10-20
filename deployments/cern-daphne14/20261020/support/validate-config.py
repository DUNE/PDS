from pathlib import Path
import os,json
import conffwk,appmodel_dal
root=Path('/nfs/home/np04daq/vst/daphne14-pds-ta-charge-20261020');cfg=root/'config';os.environ['DUNEDAQ_DB_PATH']=str(cfg)+':'+os.environ['DUNEDAQ_DB_PATH']
file=str(cfg/'sessions/pds-vst-session.data.xml');db=conffwk.Configuration('oksconflibs:'+file);session=db.get_dal('Session','pds-daphne14');disabled={x.id for x in session.disabled};report={}
for app in db.get_dals('SmartDaqApplication'):
 if app.id in disabled:continue
 print('Generating',app.id,flush=True)
 d=conffwk.Configuration('oksconflibs:'+file);a=d.get_dal(app.className(),app.id);s=d.get_dal('Session','pds-daphne14');modules=appmodel_dal.generate_modules(d,a,s)
 report[app.id]=[{'id':m.id,'class':m.className()} for m in modules]
 if app.id=='mlt':assert not any(m.className()=='RandomTCMakerModule' for m in modules)
 if app.id=='charge-emu':assert any(m.className()=='FDFakeReaderModule' for m in modules) and not any(m.className()=='DPDKReaderModule' for m in modules)
 if app.id=='runp02srv001eth1':
  handlers=[m for m in modules if m.className()=='FDDataHandlerModule'];assert len(handlers)==4 and all(m.post_processing_enabled for m in handlers)
  th=[m for m in modules if m.className()=='TriggerDataHandlerModule'];assert len(th)==1 and th[0].post_processing_enabled
 if app.id=='tc-maker-pds':assert any(m.className()=='TriggerDataHandlerModule' for m in modules)
(root/'evidence/module-generation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
