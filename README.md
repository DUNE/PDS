# PDS Runner

Photon Detection System configuration and automation for the DAPHNE front-end board.

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
