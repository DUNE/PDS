from __future__ import annotations

import logging
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

_LOG = logging.getLogger(__name__)


@dataclass
class SSPConf:
    object_name: str = "np02-ssp-on"
    number_channels: int = 12
    channel_mask: int = 1
    pulse_mode: str = "single"
    burst_count: int = 1
    double_pulse_delay_ticks: int = 0
    pulse1_width_ticks: int = 5
    pulse2_width_ticks: int = 0
    pulse_bias_percent_270nm: int = 4000
    pulse_bias_percent_367nm: int = 0

    @classmethod
    def from_config(cls, cfg: dict[str, Any]) -> "SSPConf":
        inst = cls()
        for k, v in cfg.get("ssp_conf", {}).items():
            if hasattr(inst, k):
                setattr(inst, k, int(v) if isinstance(v, str) and v.isdigit() else v)
        return inst


def run_set_ssp_conf(cfg: dict[str, Any], **overrides: Any) -> None:
    if cfg.get("skip_ssp_conf"):
        _LOG.info("  Skipping set_ssp_conf (skip_ssp_conf=True)...")
        return

    conf = SSPConf.from_config(cfg)
    for k, v in overrides.items():
        if v is not None and hasattr(conf, k):
            setattr(conf, k, v)

    cmd = ["set_ssp_conf", f"{cfg['drunc_working_dir']}/{cfg['oks_file']}"]
    for k, v in asdict(conf).items():
        cmd += [f"--{k.replace('_', '-')}", str(v)]

    _LOG.info("📢 set_ssp_conf command: %s", " ".join(cmd))
    subprocess.run(cmd, check=True, text=True)
