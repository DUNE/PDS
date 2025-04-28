from __future__ import annotations

import json
import logging
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Optional

from pds.core.set_daphne_conf import main as run_daphne_config
from pds.core.utils import pretty_compact_json
from pds.core.constants import CONFIGURATIONS


# ──────────────────────────────────────────────────────────────────────────────
# Typed container for set_ssp_conf options
# ──────────────────────────────────────────────────────────────────────────────
@dataclass(slots=True)
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


# ──────────────────────────────────────────────────────────────────────────────
# Simple wrappers around external shell tools
# ──────────────────────────────────────────────────────────────────────────────
class WebProxy:
    @staticmethod
    def setup(cfg: dict[str, Any]) -> None:
        if cfg.get("skip_proxy", False):
            logging.warning("⚠️  skip_proxy=True – not sourcing web proxy.")
            return
        cmd = ["bash", "-c", f"cd {cfg['drunc_working_dir']} && {cfg['web_proxy_cmd']}"]
        logging.info("📢  Sourcing web_proxy …")
        subprocess.run(cmd, check=True)
        logging.info("✅  Web proxy sourced.")


class DTSButler:
    def __init__(self, cfg: dict[str, Any]) -> None:
        self.cfg = cfg
        wd = cfg["drunc_working_dir"]
        self.mode = cfg.get("mode")
        self.align_cmd   = ["bash", "-c", f"cd {wd} && {cfg['dts_align_cmd']}"]
        self.fake_cmd_tpl = ["bash", "-c", f"cd {wd} && {cfg['dts_faketrig_cmd_template']}"]
        self.clear_cmd   = ["bash", "-c", f"cd {wd} && {cfg['dts_clear_fktrig_cmd']}"]

    def run(self) -> None:
        if self.mode == "cosmics":
            logging.warning("⚠️  Cosmics run – skipping DTS alignment.")
            self.clear()
            return
        logging.info("📢  DTS alignment …")
        subprocess.run(self.align_cmd, check=True)
        cmd = self.fake_cmd_tpl.copy()
        cmd[-1] = cmd[-1].format(hztrigger=self.cfg["hztrigger"])
        subprocess.run(cmd, check=True)
        logging.info("✅  DTS fake-trigger configured.")

    def clear(self) -> None:
        subprocess.run(self.clear_cmd, check=False)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────
def update_temp_details(details_in: Path, details_out: Path, mode: str) -> None:
    data = json.loads(details_in.read_text())
    for dev in data.get("devices", []):
        xcorr = dev.setdefault("self_trigger", {}).setdefault("self_trigger_xcorr", {})
        if mode == "cosmics":
            xcorr.update(correlation_threshold=4000, discrimination_threshold=5000)
        elif mode in ("noise", "calibration"):
            xcorr.update(correlation_threshold=268_435_455, discrimination_threshold=10)
    details_out.write_text(pretty_compact_json(data))
    logging.info("✅  temp_details.json → %s", details_out)


def generate_drunc_command(cfg: dict[str, Any]) -> str:
    return (
        "drunc-unified-shell ssh-standalone "
        f"{cfg['oks_session']} {cfg['session_name']} np02-pds "
        "boot conf start enable-triggers change-rate --trigger-rate "
        f"{cfg['change_rate']} wait {cfg['wait_time']} "
        "disable-triggers drain-dataflow stop-trigger-sources stop scrap terminate"
    )


def run_drunc_command(cfg: dict[str, Any], *, post_delay_s: int = 20) -> None:
    subprocess.run(
        generate_drunc_command(cfg),
        shell=True,
        cwd=cfg["drunc_working_dir"],
        check=True,
    )
    time.sleep(post_delay_s)


def run_set_ssp_conf(cfg: dict[str, Any], **overrides: Any) -> None:
    conf = SSPConf.from_config(cfg)
    for k, v in overrides.items():
        if v is not None and hasattr(conf, k):
            setattr(conf, k, v)

    cmd = ["set_ssp_conf", f"{cfg['drunc_working_dir']}/{cfg['oks_file']}"]
    for k, v in asdict(conf).items():
        cmd += [f"--{k.replace('_', '-')}", str(v)]

    subprocess.run(cmd, check=True, text=True)


# ──────────────────────────────────────────────────────────────────────────────
# Main scan / single-run controller
# ──────────────────────────────────────────────────────────────────────────────
class ScanMaskIntensity:
    def __init__(self, cfg: dict[str, Any]) -> None:
        self.cfg       = cfg
        self.masks     = cfg.get("mask_values", [1])
        self.min_bias  = cfg.get("min_bias", 4000)
        self.max_bias  = cfg.get("max_bias", 4000)
        self.step      = cfg.get("step", 500)
        self.delay_s   = cfg.get("drunc_delay_s", 20)
        self.mode      = cfg.get("mode")

    def run(self) -> None:
        if self.mode == "calibration":
            logging.info("📢  Calibration: scanning masks × intensities …")
            for mask in self.masks:
                for bias in range(self.min_bias, self.max_bias + self.step, self.step):
                    run_set_ssp_conf(self.cfg,
                                     channel_mask=mask,
                                     pulse_bias_percent_270nm=bias)
                    run_drunc_command(self.cfg, post_delay_s=self.delay_s)
            return

        # Noise & cosmics: single run, LED OFF
        if self.mode in ("noise", "cosmics"):
            logging.info("📢  %s run – single acquisition, LED OFF.", self.mode)
            run_set_ssp_conf(self.cfg,
                             channel_mask=self.masks[0],
                             pulse_bias_percent_270nm=0)
            run_drunc_command(self.cfg, post_delay_s=self.delay_s)
            return

        # Fallback for any other mode
        logging.info("📢  %s run – single acquisition, default LED ON.", self.mode)
        run_set_ssp_conf(self.cfg,
                         channel_mask=self.masks[0],
                         pulse_bias_percent_270nm=self.min_bias)
        run_drunc_command(self.cfg, post_delay_s=self.delay_s)


# ──────────────────────────────────────────────────────────────────────────────
# main()
# ──────────────────────────────────────────────────────────────────────────────
def main(mode: Optional[str] = None, conf_path: str | Path | None = None) -> None:
    if conf_path is None:
        raise ValueError("Configuration path is required.")
    conf_path = Path(conf_path).expanduser()
    if not conf_path.exists():
        raise FileNotFoundError(conf_path)

    cfg = json.loads(conf_path.read_text())
    if mode:
        cfg["mode"] = mode

    # Use a temp workspace so we never litter the repo tree
    with TemporaryDirectory(prefix="pds-run-") as tmp:
        tmp_dir = Path(tmp)
        temp_conf   = tmp_dir / "conf_temp.json"
        temp_detail = tmp_dir / "temp_details.json"

        # --- prepare details & conf ------------------------------------------------
        details_json = conf_path.parent / Path(cfg["daphne_details"]).name
        update_temp_details(details_json, temp_detail, cfg["mode"])

        drunc_dir = Path(cfg["drunc_working_dir"]).resolve()
        try:
            cfg["daphne_details"] = str(temp_detail.relative_to(drunc_dir))
        except ValueError:
            cfg["daphne_details"] = str(temp_detail)  # fall back: absolute path

        temp_conf.write_text(json.dumps(cfg, indent=2))
        logging.info("✅  temp conf → %s", temp_conf)

        # --- run sequence ----------------------------------------------------------
        dts = DTSButler(cfg)
        try:
            dts.run()
            WebProxy.setup(cfg)
            run_daphne_config(conf_path=temp_conf, mode=mode)  # external
            ScanMaskIntensity(cfg).run()
        finally:
            dts.clear()  # always attempt to clear fake trigger


if __name__ == "__main__":  # pragma: no cover
    if len(sys.argv) < 3:
        print("Usage: python -m pds.core.run <mode> <conf.json>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
