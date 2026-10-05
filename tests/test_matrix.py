import copy
import json
from pathlib import Path
import struct
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from pds.calibration.acquisition import HDF5Acquisition
from pds.calibration.plan import compile_plan
from pds.calibration.timing import rate
import test_calibration as existing
ROOT = existing.ROOT


def matrix():
    return json.loads((ROOT / 'configs/calibration/sipm-bias-vgain-afe0.json').read_text())


class MatrixTests(unittest.TestCase):
    def test_cartesian_settings_and_alias_arbitration(self):
        p = matrix()
        steps = compile_plan(p)
        self.assertEqual(len(steps), 135)
        self.assertEqual(steps[0]['coordinates'], dict(sipm_bias=800, vgain=500))
        self.assertEqual(steps[-1]['coordinates'], dict(sipm_bias=1000, vgain=2700))
        self.assertEqual([s['target'] for s in steps[0]['settings']], [0, 0])
        aliases=copy.deepcopy(p)
        aliases['axes']=[dict(variable='bias',values=[800]),dict(variable='attenuation',values=[500])]
        self.assertEqual(compile_plan(aliases)[0]['coordinates'],dict(sipm_bias=800,vgain=500))
        self.assertEqual([s['variable'] for s in compile_plan(aliases)[0]['settings']],['sipm_bias','vgain'])
        for change in [dict(axes=[dict(variable='vgain',values=[1]),dict(variable='attenuation',values=[2])]),
                dict(settings=[dict(variable='sipm_bias',target=0,value=800)]),
                dict(axes=[dict(variable='trim',values=[0])]),
                dict(axes=[dict(variable='vgain',values=[500,500])]),
                dict(waveforms_per_channel=0)]:
            invalid = copy.deepcopy(p);invalid.update(change)
            with self.assertRaises(ValueError): compile_plan(invalid)
        p['axes'] = [dict(variable='offset',values=[1000,2000],gain=False),
            dict(variable='trim',values=[0,100],gain=True)]
        p['channels'] = [0,3]
        self.assertEqual([s['target'] for s in compile_plan(p)[0]['settings']], [0,3,0,3])

    def test_all_supported_detector_optical_pairs_and_three_dimensions(self):
        p = json.loads((ROOT / 'configs/calibration/sipm-bias-led-afe0.json').read_text())
        for detector in ('sipm_bias','vgain','attenuation','offset','trim'):
            for optical in ('led_bias_270nm','led_bias_367nm','led_width_ticks','led_channel_mask','led_second_width_ticks','led_double_pulse_delay_ticks'):
                p['settings'] = []
                p['axes'] = [dict(variable=detector,values=[0,1],gain=True),
                    dict(variable=optical,values=[1,2] if optical == 'led_burst_count' else [0,1])]
                self.assertEqual(len(compile_plan(p)), 4)
        p['axes'] = [dict(variable='sipm_bias',values=[0,1]),dict(variable='vgain',values=[0,1]),
            dict(variable='led_bias_270nm',values=[0,1])]
        self.assertEqual(len(compile_plan(p)),8)

    def test_ten_thousand_matched_events_exported_from_validated_full_window(self):
        clock,period=62500000,1280
        begin=3000000;end=begin+2*clock
        def frame(ch,tick):
            return struct.pack('<3Q',(63<<52)|((ch//8)<<26),tick,(ch<<56)|(4<<52)|(2<<46))+bytes(488)
        payload=b''.join(frame(ch,t) for t in range(begin+100,end,period) for ch in [0,3])
        header=types.SimpleNamespace(fragment_type=1,element_id=types.SimpleNamespace(id=800),window_begin=begin,window_end=end,status_bits=0)
        frag=types.SimpleNamespace(get_header=lambda:header,get_data_bytes=lambda:payload)
        class Raw:
            def __init__(self,path):pass
            def get_all_record_ids(self):return [0]
            def get_fragment_dataset_paths(self,record):return [0]
            def get_frag(self,path):return frag
        modules={'hdf5libs':types.SimpleNamespace(HDF5RawDataFile=Raw),'daqdataformats':types.SimpleNamespace(FragmentType=types.SimpleNamespace(kDAPHNEEth=types.SimpleNamespace(value=1)))}
        with tempfile.TemporaryDirectory() as directory,patch.dict(sys.modules,modules):
            base=Path(directory);(base/'daq.hdf5').touch()
            acq=HDF5Acquisition(base,base/'out',[800],3)
            p=matrix();p['clock_hz']=clock;p['window_s']=2;acq.preflight(p)
            metadata=dict(step_id=0,channels=[0,3],window_s=2,capture_tail_ms=20,waveforms_per_channel=10000,coordinates=dict(sipm_bias=800,vgain=500))
            started=dict(ready_tick=1000000,period_ticks=period,clock_hz=clock,actual_rate_hz=clock/period)
            receipt=acq.collect(metadata,started)
            self.assertEqual(receipt['received_counts'],{'0':10000,'3':10000})
            self.assertEqual(receipt['coordinates'],metadata['coordinates'])
            self.assertEqual(Path(receipt['dataset']).stat().st_size,20000*512)
            self.assertGreater(receipt['source_window_counts']['0'],10000)
            self.assertEqual(receipt['expected_per_channel'],10000)
            output=Path(receipt['dataset']).read_bytes()
            expected=b''.join(frame(ch,t) for t in range(begin+100,begin+100+10000*period,period) for ch in [0,3])
            self.assertEqual(output,expected)
            metadata['window_s']=.1
            with self.assertRaisesRegex(RuntimeError,'window too short'):
                acq.collect(metadata,started)


if __name__=='__main__':unittest.main()
