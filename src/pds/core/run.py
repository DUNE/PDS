from __future__ import annotations

import logging
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional

from .butler import DTSButler
from .plan import load_config, log_plan
from .scans import AttenuatorScan, OffsetScan, SelfTriggerScan, TrimScan

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


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
            elif cfg.mode == "cosmics":
                logging.info("Cosmics mode not implemented in refactor; skipping actions for test/dry-run.")
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
