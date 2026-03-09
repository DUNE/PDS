# Configuration layout

Each facility has its own folder under `configs/` with:
- `00_paths.json`: drunc/DAPHNE/DB locations (working dir, db_folder, oks_segment_file, session_name, drunc_target, daphne_details)
- `01_commands.json`: common commands (web proxy, DTS align/fake/clear)
- `03_default_config.json`: base DAPHNE detail/config file used for all scans in that facility
- Scan configs (`04_stthre.json`, `05_attenuation.json`, `06_led_calib.json`, `07_offset.json`, `08_trim.json`, etc.): only the scan bounds/mask overrides and `facility` + `daphne_obj`. Paths/commands/defaults are auto-loaded from the numbered files.

For LED calibration scans, `02_run_defaults.json` provides the base `ssp_conf`. A compact config can define:
- `scan.mask_values`: channel-mask list
- `scan.led_intensities`: `{ "min": ..., "max": ..., "step": ... }` or `{ "values": [...] }`

You can also run directly from `02_run_defaults.json` with CLI overrides:
```bash
pds-run led-intensity-scan configs/vd_coldbox/02_run_defaults.json \
  --mask-values 1,2,4,8 \
  --min-led-intensity 3000 \
  --max-led-intensity 4095 \
  --led-intensity-step 500
```

Example run:
```bash
pds-run thr-scan configs/vst/04_stthre.json
```
This uses the VST `00_paths.json`, `01_commands.json`, and `03_default_config.json` automatically.

## Pre-run checklist (plan-only)
1. Set `"plan_only": true` in the scan config.
2. Run the command; verify logs:
   - DAPHNE changes: old → new fields for the target `daphne_obj` (thresholds, attenuators, etc.).
   - Drunc command: logged in plan_only mode (not executed).
   - DTS/SSP actions: logged as “would run”.
3. Confirm the detail file path and `daphne_obj` are correct for the facility.

## How DB updates happen
1. The scan computes the desired DAPHNE JSON for the targeted `daphne_obj` (only fields relevant to the scan).
2. A minimal diff is generated (field-level changes). In plan_only mode, this is only logged.
3. In execute mode, the merged JSON is written to a temp file and applied to the OKS XML via `add_daphne_conf -n <daphne_obj>`, touching only that object.
4. SSP and drunc commands run unless skipped; in plan_only they are logged but not executed.
