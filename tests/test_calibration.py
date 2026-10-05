import copy
from contextlib import nullcontext
import json
from pathlib import Path
import struct
import subprocess
import sys
import types
from unittest.mock import patch
import tempfile
import unittest

from pds.calibration.acquisition import audit_payload, HDF5Acquisition
from pds.calibration.coordinator import Coordinator
from pds.calibration.journal import Journal
from pds.calibration.plan import compile_plan
from pds.calibration.timing import rate, TimingSource
from pds.core.runtime import RuntimeControl, MASK, APPLIED, PAUSE, PAUSED, CAPABILITY, DRAINED

ROOT = Path(__file__).resolve().parents[1]


def plan():
    return json.loads((ROOT / 'configs/calibration/vgain-afe0.json').read_text())


class Bridge:
    def __init__(self):
        self.registers = {CAPABILITY: 0x43414C32, 0x88000034: 2, 0x94000020: 0x109,
            0x94000028: 7, MASK: 0x10000, APPLIED: 0x10000, PAUSE: 0x80000000, PAUSED: 0x80000000}
        self.settings, self.writes, self.records = [], [], 0
        self.loss = False
        self.status = dict(clock_source='endpoint', clocks_locked=True, endpoint_state=8,
            timestamp_valid=True, endpoint_address=21)

    def timing_status(self):
        return self.status

    def read32(self, address):
        return self.registers[PAUSED] if address == DRAINED else self.registers[address]

    def write32(self, address, value):
        self.writes.append((address, value))
        self.registers[address] = value
        if address in (MASK, PAUSE):
            self.registers[{MASK: APPLIED, PAUSE: PAUSED}[address]] = value
        return value

    def write_setting(self, setting):
        assert self.registers[PAUSED] & 255 == 255
        self.settings.append(copy.deepcopy(setting))
        return setting['value']

    def counters(self, channels):
        return {str(ch): dict(records=self.records - int(self.loss and ch == 3), busy=0, full=0) for ch in channels}


class Timing:
    def __init__(self, bridge):
        self.bridge, self.running, self.stops = bridge, False, 0

    def reserve(self):
        return nullcontext()

    def preflight(self):
        return dict(clock_hz=62500000)

    def start(self):
        self.running = True
        return dict(ready_tick=1000000, period_ticks=10752, clock_hz=62500000, actual_rate_hz=rate(62500000, 0, 41)[0])

    def stop(self):
        if not self.running:
            return None
        self.running = False
        self.stops += 1
        return dict(sent=17, rejected=0)


class Acquisition:
    def __init__(self, bridge):
        self.bridge, self.fail, self.metadata = bridge, False, []

    def preflight(self, plan):
        return dict(window_s=2)

    def collect(self, metadata, started):
        self.metadata.append(metadata)
        if self.fail:
            raise TimeoutError('No complete DAQ window')
        self.bridge.records += 17
        return dict(verified=True, window_begin=2000000, window_end=127000000,
            received_counts={str(ch): 17 for ch in metadata['channels']})


class CalibrationTests(unittest.TestCase):
    def execute(self, config=None, bridge=None, fail=False):
        config, bridge = config or plan(), bridge or Bridge()
        timing, acquisition = Timing(bridge), Acquisition(bridge)
        acquisition.fail = fail
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'scan.jsonl'
            journal = Journal(path)
            try:
                Coordinator(RuntimeControl(bridge, sleep=lambda _: None), timing, acquisition,
                    journal, sleep=lambda _: None).run(config)
            except BaseException as error:
                result_error = error
            else:
                result_error = None
            finally:
                journal.close()
            events = [json.loads(line) for line in path.read_text().splitlines()]
        return bridge, timing, acquisition, events, result_error

    def test_full_requested_scan_keeps_unrelated_afe_and_waits_for_receipts(self):
        bridge, timing, acquisition, events, error = self.execute()
        self.assertIsNone(error)
        self.assertEqual([s['value'] for s in bridge.settings], list(range(500, 2501, 100)))
        self.assertEqual(timing.stops, 21)
        self.assertTrue(all(m['channels'] == [0, 3] and m['window_s'] == 2 for m in acquisition.metadata))
        self.assertEqual(bridge.registers[MASK], 0x10009)
        self.assertEqual(bridge.registers[PAUSE], 0x800000FF)
        self.assertEqual(events[-1]['event'], 'scan_complete')
        self.assertEqual(sum(e['event'] == 'step_complete' for e in events), 21)
        self.assertEqual([e['sequence'] for e in events], list(range(1, len(events) + 1)))

    def test_missing_daq_window_stops_timing_and_does_not_advance_or_restore(self):
        bridge, timing, acquisition, events, error = self.execute(fail=True)
        self.assertIsInstance(error, TimeoutError)
        self.assertEqual([s['value'] for s in bridge.settings], [500])
        self.assertFalse(timing.running)
        self.assertEqual(bridge.registers[PAUSE] & 255, 255)
        self.assertEqual(events[-1]['event'], 'scan_failed')
        self.assertFalse(any(e['event'] == 'step_complete' for e in events))

    def test_capture_loss_stops_before_next_setting(self):
        bridge = Bridge()
        original = bridge.counters
        def counters(channels):
            bridge.loss = bridge.records > 0
            return original(channels)
        bridge.counters = counters
        bridge, _, _, events, error = self.execute(bridge=bridge)
        self.assertIsInstance(error, RuntimeError)
        self.assertEqual(len(bridge.settings), 1)
        self.assertEqual(events[-1]['event'], 'scan_failed')

    def test_explicit_new_physics_values(self):
        config = plan()
        config['values'] = [500]
        config['final'] = dict(mode='physics', settings=[dict(variable='vgain', target=0, value=1300)], settle_ms=10)
        bridge, _, _, _, error = self.execute(config)
        self.assertIsNone(error)
        self.assertEqual([s['value'] for s in bridge.settings], [500, 1300])
        self.assertEqual(bridge.registers[MASK], 0x10000)
        self.assertEqual(bridge.registers[PAUSE], 0x80000000)

    def test_preflight_no_writes_for_unaligned_or_local_clock(self):
        for key, value in [('endpoint_state', 6), ('clock_source', 'local'), ('timestamp_valid', False)]:
            bridge = Bridge()
            bridge.status[key] = value
            bridge, _, _, _, error = self.execute(bridge=bridge)
            self.assertIsInstance(error, RuntimeError)
            self.assertEqual(bridge.writes, [])
            self.assertEqual(bridge.settings, [])

    def test_recovery_requires_explicit_state_reconciliation(self):
        bridge = Bridge()
        bridge.registers[PAUSE] |= 1
        bridge, _, _, _, error = self.execute(bridge=bridge)
        self.assertIsInstance(error, RuntimeError)
        self.assertEqual(bridge.writes, [])

    def test_invalid_final_and_offset_gain_rejected_before_io(self):
        for final in [dict(mode='physics', settings=[dict(variable='vgain', target=1, value=1000)], settle_ms=0), dict(mode='restore')]:
            config = plan()
            config['final'] = final
            bridge, _, _, _, error = self.execute(config)
            self.assertIsInstance(error, ValueError)
            self.assertEqual(bridge.writes, [])
        config = plan()
        config.update(variable='offset', channels=[0, 3], gain=True)
        self.assertEqual([s['target'] for s in compile_plan(config)[0]['settings']], [0, 3])
        config.pop('gain')
        with self.assertRaises(ValueError):
            compile_plan(config)

    def test_existing_journal_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'scan.jsonl'
            journal = Journal(path)
            journal.record('test')
            journal.close()
            with self.assertRaises(FileExistsError):
                Journal(path)

    def test_waveform_audit_rejects_gaps_duplicates_and_wrong_tags(self):
        begin, end, period = 1000000, 126000000, 10496
        def frame(ch, tick, tag=2):
            return struct.pack('<3Q', (63 << 52) | ((ch // 8) << 26), tick,
                (ch << 56) | (4 << 52) | (tag << 46)) + bytes(488)
        ticks = list(range(begin + 100, end, period))
        payload = b''.join(frame(ch, tick) for tick in ticks for ch in (0, 3))
        selected, counts = audit_payload(payload, [0, 3], (begin, end), period)
        self.assertEqual(len(selected), len(payload))
        self.assertEqual(counts, {'0': len(ticks), '3': len(ticks)})
        for invalid in [payload[:5120] + payload[6144:], payload + payload[:512],
                frame(0, ticks[0], 1) + payload[512:],
                frame(0, ticks[0], 3) + payload[512:], payload[:-1]]:
            with self.assertRaises(RuntimeError):
                audit_payload(invalid, [0, 3], (begin, end), period)


    def test_timing_process_stops_when_sc_requests_stop(self):
        class Source(TimingSource):
            def _spawn(self, inspect=False):
                script = "import sys,json;print('diagnostic',flush=True);print('PDS_TIMING '+json.dumps({'event':'started'}),flush=True);sys.stdin.readline();print('PDS_TIMING '+json.dumps({'event':'stopped','sent':3,'rejected':0}),flush=True)"
                self.process = subprocess.Popen([sys.executable, '-u', '-c', script], stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE, bufsize=0)
                self.buffer = b''
        source = Source({}, 1)
        self.assertEqual(source.start()['event'], 'started')
        self.assertEqual(source.stop()['sent'], 3)
        self.assertIsNone(source.process)
        self.assertIsNone(source.stop())

    def test_hdf5_collector_discards_boundary_windows_and_exports_one_clean_point(self):
        period, clock = 10752, 62500000
        started = dict(ready_tick=1000000, period_ticks=period, clock_hz=clock, actual_rate_hz=rate(clock, 0, 41)[0])
        begin = 3000000
        end = begin + 2 * clock
        frame = lambda tick: struct.pack('<3Q', 63 << 52, tick, (4 << 52) | (2 << 46)) + bytes(488)
        payload = b''.join(frame(tick) for tick in range(begin + 100, end, period))
        def fragment(window, data):
            header = types.SimpleNamespace(fragment_type=1, element_id=types.SimpleNamespace(id=800),
                window_begin=window[0], window_end=window[1], status_bits=0)
            return types.SimpleNamespace(get_header=lambda: header, get_data_bytes=lambda: data)
        old, good = fragment((0, 2 * clock), payload), fragment((begin, end), payload)
        class Raw:
            def __init__(self, path): pass
            def get_all_record_ids(self): return [0, 1]
            def get_fragment_dataset_paths(self, record): return [record]
            def get_frag(self, record): return [old, good][record]
        modules = {'hdf5libs': types.SimpleNamespace(HDF5RawDataFile=Raw),
            'daqdataformats': types.SimpleNamespace(FragmentType=types.SimpleNamespace(kDAPHNEEth=types.SimpleNamespace(value=1)))}
        with tempfile.TemporaryDirectory() as directory, patch.dict(sys.modules, modules):
            base = Path(directory)
            (base / 'daq.hdf5').touch()
            acquisition = HDF5Acquisition(base, base / 'datasets', [800], 3)
            config = plan()
            config['clock_hz'] = clock
            acquisition.preflight(config)
            metadata = dict(step_id=0, channels=[0], window_s=2, capture_tail_ms=20, settings=[dict(variable='vgain', target=0, value=500)])
            receipt = acquisition.collect(metadata, started)
            self.assertEqual(receipt['record_id'], '1')
            self.assertEqual(Path(receipt['dataset']).read_bytes(), payload)
            self.assertTrue(receipt['verified'])
            self.assertEqual(receipt['schema'], 'pds.calibration.step.v1')
            self.assertEqual((receipt['frame_version'], receipt['adc_offset_bytes'],
                receipt['adc_bits'], receipt['samples_per_frame'], receipt['timing_tag']), (4, 64, 14, 256, 2))
            self.assertTrue(Path(receipt['dataset']).with_suffix('.json').exists())
            self.assertIn((str(base / 'daq.hdf5'), '0'), acquisition.used)


if __name__ == '__main__':
    unittest.main()
