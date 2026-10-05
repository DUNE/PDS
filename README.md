# PDS Runner

Photon Detection System configuration and automation for the DAPHNE front-end board.

The canonical calibration workflow is **one continuous DAQ run with SC/CCM-owned
runtime scans**, on branch `marroyav/calibration`. Use `pds-calibrate` and the
[calibration recipe](docs/calibration-scans.md) to select channels, change settings,
and label complete stable DAQ windows. The server remains a hardware bridge.

The older run-per-point calibration commands are deprecated. Ordinary run startup,
configuration generation and hardware configuration remain available.

## Installation

```bash
pip install .
```

## Usage

### Run data acquisition

```bash
pds-run run --mode cosmics --conf path/to/conf.json
```

### Generate configuration files

```bash
pds-run seed --details path/to/details.json
```

### Apply configuration settings

```bash
pds-run set --conf path/to/conf.json
```

### Install shell autocompletion

```bash
pds-run --install-completion
```

### Run tests

```bash
pip install pytest
pytest
```

## Calibration data

Keep packed raw waveforms and step metadata as the source dataset. Use the compiled
`rawdatautils.unpack.daphneeth` decoder to obtain `uint16` ADC arrays for analysis;
Waffles consumes these arrays and their calibration labels. See
[unpacking](docs/calibration-scans.md#unpacking).

For local HDF5-to-binary conversion without a DAQ environment, build the
[standalone C++ reader](tools/hdf5_unpack/README.md).
