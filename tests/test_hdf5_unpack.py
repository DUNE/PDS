"""Standalone decoder tests; set PDS_HDF5_UNPACK to the built executable."""
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
try:
    import h5py
    import numpy as np
except ImportError:
    h5py = np = None

EXECUTABLE = os.environ.get('PDS_HDF5_UNPACK')


@unittest.skipUnless(EXECUTABLE and h5py is not None, 'Built reader, h5py and NumPy are required')
class HDF5UnpackTests(unittest.TestCase):
    def fixture(self, status=0):
        values = [(i * 197 + 31) & 0x3fff for i in range(256)]
        values[:2] = [0, 16383]
        packed = sum(value << (14 * i) for i, value in enumerate(values)).to_bytes(448, 'little')
        frame = struct.pack('<3Q', 63 << 52, 1000000, (4 << 52) | (2 << 46)) + bytes(range(40)) + packed
        header = bytearray(72)
        struct.pack_into('<IIQ', header, 0, 0x11112222, 6, len(frame) + len(header))
        struct.pack_into('<II', header, 52, status, 18)
        struct.pack_into('<I', header, 68, 800)
        return bytes(header) + frame, values

    def run_reader(self, source, output):
        return subprocess.run([EXECUTABLE, str(source), str(output)], capture_output=True, text=True)

    def test_signed_unsigned_compressed_data_and_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory) / 'input.hdf5', Path(directory) / 'decoded'
            blob, values = self.fixture(status=18)
            with h5py.File(source, 'w') as raw:
                raw.create_dataset('signed', data=np.frombuffer(blob, dtype='i1').reshape(-1, 1), compression='gzip')
                raw.create_dataset('unsigned', data=np.frombuffer(blob, dtype='u1'), compression='gzip')
            result = self.run_reader(source, output)
            self.assertEqual(result.returncode, 0, result.stderr)
            np.testing.assert_array_equal(np.fromfile(output / 'adc.u16.bin', '<u2').reshape(2, 256), [values, values])
            self.assertEqual((output / 'header.u8.bin').read_bytes(), blob[72:136] * 2)
            manifest = json.loads((output / 'manifest.json').read_text())
            self.assertEqual((manifest['waveforms'], manifest['flagged_fragments']), (2, 2))
            self.assertTrue(manifest['complete'])
            self.assertEqual(np.fromfile(output / 'timestamp.u64.bin', '<u8').tolist(), [1000000, 1000000])
            self.assertNotEqual(self.run_reader(source, output).returncode, 0)
            np.testing.assert_array_equal(np.fromfile(output / 'adc.u16.bin', '<u2').reshape(2, 256), [values, values])

    def test_rejects_truncated_and_incompatible_formats(self):
        valid, _ = self.fixture()
        mutations = [bytearray(valid) for _ in range(4)]
        struct.pack_into('<I', mutations[0], 4, 5)
        mutations[1][94] = (mutations[1][94] & 15) | 16
        mutations[2] = mutations[2][:-1]
        struct.pack_into('<Q', mutations[2], 8, len(mutations[2]))
        struct.pack_into('<Q', mutations[3], 72, (63 << 52) | (1 << 26))
        with tempfile.TemporaryDirectory() as directory:
            for index, blob in enumerate(mutations):
                source, output = Path(directory) / f'bad-{index}.hdf5', Path(directory) / f'out-{index}'
                with h5py.File(source, 'w') as raw:
                    raw.create_dataset('DAPHNEEth', data=np.frombuffer(blob, dtype='u1'))
                self.assertNotEqual(self.run_reader(source, output).returncode, 0)
                self.assertNotIn('"complete":true', (output / 'manifest.json').read_text())
