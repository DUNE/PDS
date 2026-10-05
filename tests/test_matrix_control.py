import copy
import json
from pathlib import Path
import tempfile
import unittest

from pds.calibration.coordinator import Coordinator
from pds.calibration.plan import compile_plan
from pds.calibration.journal import Journal
from pds.core.runtime import RuntimeControl
import test_calibration as existing


class MatrixControlTests(unittest.TestCase):
    def execute(self, short=False, failed_optical=False, daphne_command=7):
        plan=json.loads((existing.ROOT/'configs/calibration/sipm-bias-led-afe0.json').read_text())
        plan['channels']=[0,3]
        plan['timing']['command_id']=daphne_command
        plan['axes']=[dict(variable='sipm_bias',values=[800,900]),dict(variable='led_bias_270nm',values=[0,1000])]
        bridge=existing.Bridge();optical=[]
        bridge.registers[0x94000028]=daphne_command
        class Timing(existing.Timing):
            def stop(self):
                event=super().stop()
                if event:event['sent']=10000
                return event
        class Acquisition(existing.Acquisition):
            def collect(self,metadata,started):
                self.metadata.append(copy.deepcopy(metadata))
                self.bridge.records+=10000
                return dict(verified=True,received_counts={'0':9999 if short else 10000,'3':10000})
        def apply_optical(settings):
            self.assertEqual(bridge.registers[0xA0010F0C]&255,255)
            optical.append(copy.deepcopy(settings))
            # Independent clock and unrelated event count: neither is compared with DAPHNE.
            return dict(verified=not failed_optical,settings=settings,clock_timestamp=42,commands=123)
        timing=Timing(bridge);acquisition=Acquisition(bridge)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'scan.jsonl';journal=Journal(path)
            runner=Coordinator(RuntimeControl(bridge,sleep=lambda _:None),timing,acquisition,journal,
                sleep=lambda _:None,apply_optical=apply_optical)
            try:runner.run(plan)
            except RuntimeError as error:result=error
            else:result=None
            finally:journal.close()
            events=[json.loads(line) for line in path.read_text().splitlines()]
        return bridge,timing,acquisition,optical,events,result

    def test_independent_domains_share_command_id_without_matching_counts(self):
        bridge,timing,acquisition,optical,events,error=self.execute()
        self.assertIsNone(error)
        self.assertEqual(len(acquisition.metadata),4)
        self.assertEqual(acquisition.metadata[1]['coordinates'],dict(sipm_bias=800,led_bias_270nm=1000))
        for metadata in acquisition.metadata:
            self.assertEqual(metadata['command_id'],7)
            self.assertEqual(metadata['optical_timing'],dict(domain='ssp',command_id=7))
            self.assertEqual(metadata['timing_domain'],'daphne')
            self.assertEqual(metadata['illumination']['commands'],123)
        self.assertTrue(all(s['variable'] in ('vgain','sipm_bias') for s in bridge.settings))
        self.assertEqual(events[-1]['event'],'scan_complete')
        self.assertEqual(len(optical),4)  # No automatic optical restore/final transaction.
        self.assertFalse(timing.running)
        self.assertEqual(bridge.registers[0x94000028],7)
        self.assertFalse(any(address==0x94000028 for address,value in bridge.writes))

    def test_alternative_daphne_command_is_an_explicit_configuration(self):
        bridge,timing,acquisition,optical,events,error=self.execute(daphne_command=9)
        self.assertIsNone(error)
        for metadata in acquisition.metadata:
            self.assertEqual(metadata['command_id'],9)
            self.assertEqual(metadata['optical_timing']['command_id'],7)
        self.assertEqual(bridge.registers[0x94000028],9)
        self.assertFalse(any(address==0x94000028 for address,value in bridge.writes))

    def test_invalid_optical_domain_and_command_fail_before_io(self):
        plan=json.loads((existing.ROOT/'configs/calibration/sipm-bias-led-afe0.json').read_text())
        for timing in [dict(domain='daphne',command_id=7),dict(domain='ssp',command_id=9)]:
            invalid=copy.deepcopy(plan);invalid['illumination']['timing']=timing
            with self.assertRaises(ValueError):compile_plan(invalid)

    def test_unacknowledged_settings_or_short_dataset_stop_before_next_point(self):
        for kwargs in (dict(short=True),dict(failed_optical=True)):
            bridge,timing,acquisition,optical,events,error=self.execute(**kwargs)
            self.assertIsInstance(error,RuntimeError)
            self.assertEqual(len(optical),1)
            self.assertLessEqual(len(acquisition.metadata),1)
            self.assertEqual(events[-1]['event'],'scan_failed')
            self.assertFalse(timing.running)
            self.assertEqual(bridge.registers[0xA0010F0C]&255,255)
            self.assertFalse(any(e['event']=='step_complete' for e in events))


if __name__=='__main__':unittest.main()
