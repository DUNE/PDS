from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional

from .butler import DTSButler
from .plan import load_config, log_plan
from .scans import AttenuatorScan, LedIntensityScan, OffsetScan, SelfTriggerScan, TrimScan
from .daphne import apply_daphne_patch
from .drunc import run_drunc_command

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def _run_single_mode(cfg, conf_path: Path, *, tmp_dir: Path) -> None:
    """Apply the DAPHNE config once, then run drunc."""
    raw_conf = json.loads(conf_path.read_text())
    if not getattr(cfg, "daphne_obj", None):
        obj = raw_conf.get("daphne_obj")
        if obj:
            cfg.daphne_obj = obj  # type: ignore[attr-defined]
        else:
            raise ValueError("daphne_obj must be set in the config for run modes.")

    # Build desired DAPHNE payload from the config (drop non-DAPHNE keys).
    desired = {
        k: v
        for k, v in raw_conf.items()
        if k
        not in (
            "facility",
            "paths",
            "commands",
            "daphne_obj",
            "mode",
            "dry_run",
            "plan_only",
            "skip_dts",
            "skip_daphne_conf",
            "skip_ssp_conf",
            "mask_values",
            "drunc_delay_s",
            "scan",
        )
    }
    # If keys are board-ids, keep only those.
    board_only = {k: v for k, v in desired.items() if isinstance(k, str) and k.isdigit()}
    if board_only:
        desired = board_only

    details_path = Path(cfg.drunc_working_dir) / cfg.daphne_details
    oks_file = cfg.resolved_oks_file()
    xml_path = Path(cfg.drunc_working_dir) / oks_file if oks_file else Path(cfg.drunc_working_dir)

    def _deep_update(dst, src):
        for k, v in src.items():
            if isinstance(v, dict) and isinstance(dst.get(k), dict):
                _deep_update(dst[k], v)
            else:
                dst[k] = v

    def _mutate(data):
        # Merge desired into existing details to preserve required fields (e.g., channel_analog_conf)
        _deep_update(data, desired)

    apply_daphne_patch(
        cfg,
        details_path=details_path,
        xml_path=xml_path,
        tmp_dir=tmp_dir,
        mutate=_mutate,
        description=cfg.mode,
    )

    cfg_dict = cfg.model_dump(mode="python")
    if oks_file:
        cfg_dict["oks_file"] = oks_file
    run_drunc_command(cfg_dict, post_delay_s=cfg.drunc_delay_s)


def main(mode: Optional[str] = None, conf_path: str | Path | None = None) -> None:
    if conf_path is None:
        if len(sys.argv) < 3:
            print("Usage: python -m pds.core.run <mode> <conf.json>")
            sys.exit(1)
        mode = sys.argv[1]
        conf_path = sys.argv[2]

    conf_path = Path(conf_path)
    cfg = load_config(conf_path, mode_override=mode)
    run_id = log_plan(cfg)

    with TemporaryDirectory(prefix="pds-run-") as tmp:
        tmp_dir = Path(tmp)

        dts = DTSButler(
            workdir=Path(cfg.drunc_working_dir),
            align_cmd=str(cfg.__dict__.get("dts_align_cmd", "") or ""),
            fake_cmd_tpl=str(cfg.__dict__.get("dts_faketrig_cmd_template", "") or ""),
            clear_cmd=str(cfg.__dict__.get("dts_clear_fktrig_cmd", "") or ""),
            mode=cfg.mode,
            skip=cfg.skip_dts,
        )

        try:
            if cfg.plan_only:
                logging.info("plan_only=True; skipping Butler run commands...")
            elif not cfg.skip_dts and not cfg.dry_run:
                dts.run(hztrigger=cfg.__dict__.get("hztrigger"))
            else:
                logging.info("  Skipping Butler run commands...")

            if cfg.mode in ("thrscan", "threshold", "sthscan", "selftrigger"):
                SelfTriggerScan(cfg, tmp_dir=tmp_dir).run()
            elif cfg.mode in ("attscan", "attenuator"):
                AttenuatorScan(cfg, tmp_dir=tmp_dir).run()
            elif cfg.mode == "offsetscan":
                OffsetScan(cfg, tmp_dir=tmp_dir).run()
            elif cfg.mode == "trimscan":
                TrimScan(cfg, tmp_dir=tmp_dir).run()
            elif cfg.mode in ("calibrun", "ledrun", "ledintscan", "ledscan"):
                LedIntensityScan(cfg, tmp_dir=tmp_dir).run()
            elif cfg.mode == "cosmics":
                _run_single_mode(cfg, conf_path, tmp_dir=tmp_dir)
            else:
                raise ValueError(f"Unsupported mode '{cfg.mode}'")
        finally:
            if cfg.plan_only:
                logging.info("plan_only=True; skipping Butler clear commands...")
            elif not cfg.skip_dts and not cfg.dry_run:
                dts.clear()
            else:
                logging.info("  Skipping Butler clear commands...")


if __name__ == "__main__":  # pragma: no cover
    if len(sys.argv) < 3:
        print("Usage: python -m pds.core.run <mode> <conf.json>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
