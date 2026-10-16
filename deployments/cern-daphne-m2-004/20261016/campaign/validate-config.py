#!/usr/bin/env python3
"""Load the private OKS profiles and generate DAQ modules without booting apps."""
import json,os,tempfile,shutil,sys
from pathlib import Path
import conffwk
import appmodel_dal

ROOT=Path(__file__).resolve().parent
report={}
for profile in ['calibration']:
    with tempfile.TemporaryDirectory(prefix='m2-004-oks-') as temp:
        cfg=Path(temp)/'db';shutil.copytree(ROOT/'config'/profile,cfg)
        original=os.environ.get('DUNEDAQ_DB_PATH','')
        os.environ['DUNEDAQ_DB_PATH']=str(cfg)+':'+original
        db=conffwk.Configuration('oksconflibs:'+str(cfg/'sessions/pds-vst-session.data.xml'))
        session=db.get_dal('Session','pds-m2-004')
        disabled={x.id for x in session.disabled}
        apps=db.get_dals('SmartDaqApplication')
        modules={}
        for app in apps:
            if app.id not in disabled:
                # Runtime generation uses an independent DB for each process.
                # Common connection IDs otherwise collide between applications.
                appdb=conffwk.Configuration('oksconflibs:'+str(cfg/'sessions/pds-vst-session.data.xml'))
                app_session=appdb.get_dal('Session','pds-m2-004')
                app_object=appdb.get_dal(app.className(),app.id)
                print('Generating',profile,app.id,flush=True)
                generated=appmodel_dal.generate_modules(appdb,app_object,app_session)
                modules[app.id]=[{'id':x.id,'class':x.className()} for x in generated]
                if app.id=='runp02srv001eth1':
                    handlers=[x for x in generated if x.className()=='FDDataHandlerModule']
                    assert len(handlers)==4,'All32 profile requires four 8-channel waveform senders across two links'
                    for handler in handlers:
                        assert handler.post_processing_enabled==(profile=='tp-test')
                        if profile=='tp-test':
                            assert any(x.data_type=='TriggerPrimitiveVector' for x in handler.outputs)
                            assert handler.raw_data_callback is not None
                    assert any(x.className()=='TriggerDataHandlerModule' for x in generated)==(profile=='tp-test')
        readout=db.get_dal('ReadoutApplication','runp02srv001eth1')
        assert readout.tp_generation_enabled==(profile=='tp-test')
        frontend=db.get_dal('DaphneV2BoardConf','daphne_mezz-daphne-m2-004-conf')
        assert (frontend.detector_id,frontend.crate_id,frontend.slot_id)==(8,4,2)
        assert frontend.address=='10.73.137.113'
        assert db.get_dal('DaphneMapEntry','daphne_mezz-daphne-m2-004-conf').key=='8.4.2'
        assert ('tp-stream-writer' in disabled)==(profile=='calibration')
        report[profile]={'oks_load':'passed','module_generation':'passed','applications':modules}
        os.environ['DUNEDAQ_DB_PATH']=original
if len(sys.argv)>1:Path(sys.argv[1]).write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
