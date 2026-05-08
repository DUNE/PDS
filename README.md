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

### Patch a configuration file

```bash
pds-run conf-update --conf path/to/conf.json --drunc-dir /path/to/workarea --set daphne_details=pds/configs/vst/detail_mezz.json
```

Use multiple `--set dotted.key=value` pairs to tweak any field without editing JSON manually. Specify `--output new.json` to keep the original file untouched.

### Run an LED intensity matrix

```bash
pds-run led-intensity-scan configs/vd_coldbox/02_run_defaults.json \
  --mask-values 1,2,4,8 \
  --min-led-intensity 3000 \
  --max-led-intensity 4095 \
  --led-intensity-step 500
```

This uses `02_run_defaults.json` for the base `ssp_conf`, infers the facility from the config path, and scans automatically over the requested LED intensities and masks. You can also store the same settings in `scan.mask_values` and `scan.led_intensities` inside a JSON config.

### VD coldbox operator guide

For the full beginner workflow, including SSH, tmux, DAQ sourcing, seed/detail JSON editing, XML overlays, and scan commands, see:

```text
docs/vd-coldbox-daq-scans.md
```

### Run VD coldbox FE scans through DAQ

The VD coldbox configs use board-keyed DAPHNE JSON, for example `"61": {...}`. The scan commands update that shape directly before calling `add_daphne_conf`, `set_ssp_conf`, and `drunc`.

```bash
pds-run att-scan configs/vd_coldbox/09_vgain_led_scan_np02_ssp.json
pds-run afe-bias-scan configs/vd_coldbox/10_afe_bias_led_scan_np02_ssp.json
```

The sample configs are `plan_only` and `dry_run` by default. Remove those guards only in the sourced DAQ runtime environment.

### Install shell autocompletion

```bash
pds-run --install-completion
```

### Run tests

```bash
pip install pytest
pytest
```
