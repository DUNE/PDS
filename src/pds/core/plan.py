from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict
from uuid import uuid4

from .config_model import ScanConfig

_LOG = logging.getLogger(__name__)


def _merge_section(cfg: Dict[str, Any], section: Dict[str, Any], keys: Dict[str, str]) -> None:
    """Populate cfg with keys from section if not already set."""
    for target, source in keys.items():
        if target not in cfg and source in section:
            cfg[target] = section[source]


def _normalize_config_data(cfg_data: Dict[str, Any]) -> Dict[str, Any]:
    """Allow modular conf.json: paths/commands/scan sections and facility defaults."""
    # If a facility is specified, load defaults from configs/{facility}/paths.json and commands.json
    facility = cfg_data.get("facility")
    if facility:
        base = Path(cfg_data.get("_base_dir", Path.cwd()))
        paths_path = base / "configs" / facility / "00_paths.json"
        commands_path = base / "configs" / facility / "01_commands.json"
        if paths_path.exists():
            paths_defaults = json.loads(paths_path.read_text())
            cfg_data.setdefault("paths", {})
            paths_section = cfg_data["paths"]
            for k, v in paths_defaults.items():
                paths_section.setdefault(k, v)
        if commands_path.exists():
            cmd_defaults = json.loads(commands_path.read_text())
            cfg_data.setdefault("commands", {})
            cmd_section = cfg_data["commands"]
            for k, v in cmd_defaults.items():
                cmd_section.setdefault(k, v)

    paths = cfg_data.get("paths") or cfg_data.get("directories")
    if isinstance(paths, dict):
        _merge_section(
            cfg_data,
            paths,
            {
                "drunc_working_dir": "drunc_working_dir",
                "daphne_details": "daphne_details",
                "oks_file": "oks_file",
                "oks_session": "oks_session",
                "session_name": "session_name",
                "drunc_target": "drunc_target",
                "db_folder": "db_folder",
                "oks_segment_file": "oks_segment_file",
            },
        )

    commands = cfg_data.get("commands")
    if isinstance(commands, dict):
        _merge_section(
            cfg_data,
            commands,
            {
                "web_proxy_cmd": "web_proxy_cmd",
                "dts_align_cmd": "dts_align_cmd",
                "dts_faketrig_cmd_template": "dts_faketrig_cmd_template",
                "dts_clear_fktrig_cmd": "dts_clear_fktrig_cmd",
            },
        )

    scan = cfg_data.get("scan")
    if isinstance(scan, dict):
        thresholds = scan.get("thresholds", {})
        _merge_section(
            cfg_data,
            thresholds,
            {
                "min_self_trigger_threshold": "min",
                "max_self_trigger_threshold": "max",
                "self_trigger_threshold_step": "step",
            },
        )
        att = scan.get("attenuators", {})
        _merge_section(cfg_data, att, {"min_att": "min", "max_att": "max", "att_step": "step"})
        offsets = scan.get("offsets", {})
        _merge_section(
            cfg_data,
            offsets,
            {"min_offset": "min", "max_offset": "max", "offset_step": "step"},
        )
        trims = scan.get("trims", {})
        _merge_section(cfg_data, trims, {"min_trim": "min", "max_trim": "max", "trim_step": "step"})
        if "mask_values" in scan and "mask_values" not in cfg_data:
            cfg_data["mask_values"] = scan["mask_values"]
        if "dailycalib" in scan and "dailycalib" not in cfg_data:
            cfg_data["dailycalib"] = scan["dailycalib"]

    return cfg_data


def load_config(conf_path: Path, *, mode_override: str | None = None) -> ScanConfig:
    """Load and validate the user configuration file."""
    raw = json.loads(conf_path.read_text())
    # Base dir used to resolve facility defaults (00_paths/01_commands)
    # conf: .../configs/<facility>/<file>.json -> repo root is parents[2]
    raw["_base_dir"] = conf_path.resolve().parents[2]
    if mode_override:
        raw["mode"] = mode_override
    cfg_data = _normalize_config_data(raw)
    cfg = ScanConfig(**cfg_data)
    return cfg


def log_plan(cfg: ScanConfig) -> str:
    """Emit a concise plan summary and return a run id."""
    run_id = str(uuid4())
    _LOG.info(
        "📝 Plan %s: mode=%s | skip_dts=%s skip_daphne_conf=%s skip_ssp_conf=%s dry_run=%s plan_only=%s",
        run_id,
        cfg.mode,
        cfg.skip_dts,
        cfg.skip_daphne_conf,
        cfg.skip_ssp_conf,
        cfg.dry_run,
        cfg.plan_only,
    )
    if cfg.mode in ("thrscan", "threshold", "sthscan", "selftrigger"):
        min_thr, max_thr, step = cfg.thresholds()
        _LOG.info(" thresholds: min=%s max=%s step=%s", min_thr, max_thr, step)
    if cfg.mode in ("attscan", "attenuator"):
        _LOG.info(" attenuators: min=%s max=%s step=%s", *cfg.att_range())
    if cfg.mode == "offsetscan":
        _LOG.info(" offsets: min=%s max=%s step=%s", *cfg.offset_range())
    if cfg.mode == "trimscan":
        _LOG.info(" trims: min=%s max=%s step=%s", *cfg.trim_range())
    return run_id
