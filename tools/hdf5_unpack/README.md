# Local HDF5 decoding

Build a standalone C++ reader with a C++20 compiler, CMake, Git and the HDF5 C
library. No DAQ services, Python bindings or CERN environment are needed. CMake
fetches pinned header-only format definitions. ADC bit decoding uses the same
`DAPHNEEthFrame::get_adc` accessor as `rawdatautils`.

```sh
# Debian/Ubuntu build dependencies:
sudo apt install cmake g++ git libhdf5-dev
cmake -S tools/hdf5_unpack -B build/hdf5_unpack -DCMAKE_BUILD_TYPE=Release
cmake --build build/hdf5_unpack -j2
build/hdf5_unpack/pds-hdf5-unpack input.hdf5 new-output-directory
```

The reader accepts fragment header v6 and DAPHNE Ethernet v4: 512-byte frames,
64-byte headers and 256 packed 14-bit ADC samples. Other fragment types are
ignored. Invalid frame sizes, versions or stream/channel mappings fail the
conversion. Input files are opened read-only; output directories must be new.
Memory usage is bounded by batches of 8192 waveforms rather than file size.

Outputs retain HDF5 dataset order, then waveform order within each fragment:

| File | Little-endian array shape | Contents |
| --- | --- | --- |
| `adc.u16.bin` | `(N, 256)`, uint16 | Original unsigned ADC codes, without rescaling |
| `timestamp.u64.bin` | `(N,)`, uint64 | Waveform timestamps in timing ticks |
| `channel.u8.bin` | `(N,)`, uint8 | Board-local channel numbers |
| `header.u8.bin` | `(N, 64)`, uint8 | Original headers, calibration tags and peak descriptors |
| `manifest.json` | JSON | Source IDs, run/trigger numbers, dataset paths, row ranges, windows and status bits |

Fragments with nonzero status bits are retained and identified in the manifest;
conversion does not certify their acquisition quality. Scan labels still come
from the SC/CCM journal. Only a successful exit and `complete: true` manifest
identify a completed conversion; partial output from a failed run is unusable.

```python
import numpy as np
adc = np.memmap('new-output-directory/adc.u16.bin',
                dtype='<u2', mode='r').reshape(-1, 256)
```

The executable prints read, decode/validation, write and total wall times.
Output writes are buffered and flushed on close; timings exclude filesystem
synchronization, network transfer and compilation. Warm-cache timings do not
measure cold disk throughput.

To verify every sample independently against the original HDF5 bytes:

```sh
python3 -m pip install numpy h5py
python3 tools/hdf5_unpack/check.py input.hdf5 new-output-directory
```

Run the format and failure checks against the built executable:

```sh
PDS_HDF5_UNPACK="$PWD/build/hdf5_unpack/pds-hdf5-unpack" \
  python3 -m unittest discover -s tests -p test_hdf5_unpack.py
```
