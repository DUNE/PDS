import csv
import json
from pathlib import Path
import unittest
from pds.calibration.timing import rate
ROOT = Path(__file__).resolve().parents[1]


class TimingRateTests(unittest.TestCase):
    def test_measured_timing_periods_decode_correctly(self):
        base = ROOT / 'docs/measurements/timing-rate-20261005'
        raw = [json.loads(line) for line in (base/'results.jsonl').read_text().splitlines()]
        rows = list(csv.DictReader((base/'rates.csv').read_text().splitlines()))
        for before, measured in zip(raw, rows):
            prescale = before['started']['period_ticks'] // 256
            hz, ticks = rate(62500000,0,prescale)
            self.assertEqual(ticks,int(measured['period_ticks']))
            self.assertEqual(hz,float(measured['observed_hz']))
        with self.assertRaises(RuntimeError): rate(62500000,1,41)
