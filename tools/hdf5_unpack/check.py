"""Compare all exported samples and metadata with the original HDF5 bytes."""
import hashlib
import json
from pathlib import Path
import sys
import h5py
import numpy as np

source, directory = Path(sys.argv[1]), Path(sys.argv[2])
manifest = json.loads((directory / 'manifest.json').read_text())
if manifest.get('complete') is not True:
    raise RuntimeError('Conversion did not complete')
rows = manifest['waveforms']
arrays = {name: np.memmap(directory / name, mode='r', dtype=dtype).reshape(shape)
          for name, dtype, shape in [('adc.u16.bin', '<u2', (rows, 256)),
          ('timestamp.u64.bin', '<u8', (rows,)), ('channel.u8.bin', 'u1', (rows,)),
          ('header.u8.bin', 'u1', (rows, 64))]}
bit = np.arange(256) * 14
byte, shift = bit // 8, bit % 8
checked = 0
with h5py.File(source) as raw:
    expected_paths = []
    def visit(name, dataset):
        if not isinstance(dataset, h5py.Dataset) or dataset.dtype.kind not in ('i', 'u') or dataset.dtype.itemsize != 1:
            return
        prefix = dataset[:72].tobytes()
        if len(prefix) >= 72 and int.from_bytes(prefix[:4], 'little') == 0x11112222 and int.from_bytes(prefix[56:60], 'little') == 18:
            expected_paths.append(name)
    raw.visititems(visit)
    if set(expected_paths) != {f['dataset'] for f in manifest['fragments']}:
        raise RuntimeError('Missing or duplicated HDF5 fragments')
    for fragment in manifest['fragments']:
        blob = raw[fragment['dataset']][...].tobytes()
        frames = np.frombuffer(blob[72:], dtype='u1').reshape(-1, 512)
        begin, count = fragment['first_row'], fragment['rows']
        if begin != checked or count != len(frames):
            raise RuntimeError('Incorrect fragment row mapping')
        selected = slice(begin, begin + count)
        packed = np.pad(frames[:, 64:], ((0, 0), (0, 2))).astype(np.uint32)
        # Independent byte-based reference; C++ uses the shared 64-bit accessor.
        expected = ((packed[:, byte] | packed[:, byte + 1] << 8 |
                     packed[:, byte + 2] << 16) >> shift) & 0x3fff
        words = frames.copy().view('<u8').reshape(count, 64)
        for name, values in [('adc.u16.bin', expected), ('timestamp.u64.bin', words[:, 1]),
                             ('channel.u8.bin', words[:, 2] >> 56), ('header.u8.bin', frames[:, :64])]:
            if not np.array_equal(arrays[name][selected], values):
                raise RuntimeError('Decoded data mismatch: ' + name + ' in ' + fragment['dataset'])
        for name, start, end in [('source_id', 68, 72), ('status_bits', 52, 56),
                                 ('window_begin', 32, 40), ('window_end', 40, 48)]:
            if fragment[name] != int.from_bytes(blob[start:end], 'little'):
                raise RuntimeError('Fragment metadata mismatch: ' + name)
        checked += count
if checked != rows:
    raise RuntimeError('Output row count mismatch')
unique, counts = np.unique(arrays['timestamp.u64.bin'], return_counts=True)
print(json.dumps(dict(verified=True, waveforms=rows, samples=rows * 256,
    adc_min=int(arrays['adc.u16.bin'].min()), adc_max=int(arrays['adc.u16.bin'].max()),
    unique_timestamps=len(unique), waveforms_per_timestamp=sorted(set(map(int, counts))),
    input_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
    output_sha256={name: hashlib.sha256((directory / name).read_bytes()).hexdigest() for name in arrays}), indent=2))
