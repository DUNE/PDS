# pdstools
This Python package can be used to load HDF5 files that contain DAPHNEStream data fragments using `pdstools.DAPHNEStreamData(filename)`. This package aims to contain any common PDS utilities and data loaders that will be useful for anyone processing PDS HDF5 files.

There can be potentially many warning outputs when trying to load with `DAPHNEStreamData`. These outputs can be suppressed by using `DAPHNEStreamData(filename, quiet=True)`.
## Examples
```python
import pdstools

filename = "path/to/DAPHNEStream.hdf5"

data = pdstools.DAPHNEStreamData(filename)
frag_paths = data.get_fragment_paths()  # Returns all data fragment paths in the current file
data.set_channels([0,1])  # Required. Sets channels of interest to search for.
wfs = data.load_fragment(frag_paths[0])  # Attempts to load this data fragment. Returns empty if channels are not within it.

data_quiet = pdstools.DAPHNEStreamData(filename, quiet=True)
```
