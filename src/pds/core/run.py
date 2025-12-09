from __future__ import annotations

import json
import logging
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Optional, Callable

from pds.core.set_daphne_conf import main as run_daphne_config
from pds.core.utils import pretty_compact_json, setup_led_range, getlogfile
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
    """
    Lightweight wrapper around the external `dtsbutler` helper.

    For modes “cosmics”, “thrscan” (aka “threshold”), we skip the alignment
    step entirely and only make sure any fake trigger left over from earlier
    runs is cleared.
    """

    def __init__(self, cfg: dict[str, Any]) -> None:
        self.cfg = cfg
        self.skip = bool(cfg.get("skip_dts"))
        wd = cfg["drunc_working_dir"]
        self.mode = cfg.get("mode")

        self.align_cmd    = ["bash", "-c", f"cd {wd} && {cfg['dts_align_cmd']}"]
        self.fake_cmd_tpl = ["bash", "-c", f"cd {wd} && {cfg['dts_faketrig_cmd_template']}"]
        self.clear_cmd    = ["bash", "-c", f"cd {wd} && {cfg['dts_clear_fktrig_cmd']}"]

    # ------------------------------------------------------------------ #

    def run(self) -> None:
        if self.skip:
            logging.info("  Skipping Butler alignment (skip_dts=True)...")
            return

        # Skip alignment + periodic fake-triggers in cosmics *and* threshold scans
        if self.mode in ("cosmics", "thrscan", "threshold", "sthscan", "selftrigger"):
            logging.warning("⚠️  %s run – skipping DTS alignment.", self.mode)
            self.clear()
            return

        logging.info("📢  DTS alignment …")
        subprocess.run(self.align_cmd, check=True)

        cmd = self.fake_cmd_tpl.copy()
        cmd[-1] = cmd[-1].format(hztrigger=self.cfg["hztrigger"])
        subprocess.run(cmd, check=True)
        logging.info("✅  DTS fake-trigger configured.")

    def clear(self) -> None:
        """Always safe to call; ignores errors."""
        if self.skip:
            logging.info("  Skipping Butler clear (skip_dts=True)...")
            return
        subprocess.run(self.clear_cmd, check=False)

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────
def update_temp_details(details_in: Path, details_out: Path, mode: str) -> None:
    data = json.loads(details_in.read_text())
    for dev in data.get("devices", []):
        xcorr = dev.setdefault("self_trigger", {}).setdefault("self_trigger_xcorr", {})
        if mode == "cosmics":
           pass
           # xcorr.update(correlation_threshold=4000, discrimination_threshold=5000)
        elif mode in ("noise", "ledrun", "calibrun", "attscan", "offsetscan", "trimscan"):
            xcorr.update(correlation_threshold=134217720, discrimination_threshold=10)
    details_out.write_text(pretty_compact_json(data))
    logging.info("✅  temp_details.json → %s", details_out)

def generate_drunc_command(cfg: dict[str, Any]) -> str:
    if cfg.get("dry_run"):
        return "echo '🧪 [dry-run] Simulating drunc command...'"
    return (
        "drunc-unified-shell ssh-CERN-kafka.json "
        f"{cfg['oks_session']} {cfg['session_name']} main-np02-pds "
        "start-run change-rate --trigger-rate "
        f"{cfg['change_rate']} wait {cfg['wait_time']} "
        "shutdown terminate"
    )

def run_drunc_command(cfg: dict[str, Any], *, post_delay_s: int = 20) -> None:
    cmd = generate_drunc_command(cfg)
    if cfg.get("dry_run"):
        logging.info("🧪 Dry run: %s", cmd)
        return
    logging.info(f"{cmd}")
    subprocess.run(cmd, shell=True, cwd=cfg["drunc_working_dir"], check=True)
    print(f"Sleeping for {post_delay_s} seconds. Press Ctrl+C if you need to stop...")
    try:
        time.sleep(post_delay_s)
    except KeyboardInterrupt:
        print("\nScript interrupted by user.")
        exit(0)

    print("Continuing execution...")

def run_set_ssp_conf(cfg: dict[str, Any], **overrides: Any) -> None:
    if cfg.get("skip_ssp_conf"):
        logging.info("  Skipping set_ssp_conf (skip_ssp_conf=True)...")
        return

    conf = SSPConf.from_config(cfg)
    for k, v in overrides.items():
        if v is not None and hasattr(conf, k):
            setattr(conf, k, v)

    cmd = ["set_ssp_conf", f"{cfg['drunc_working_dir']}/{cfg['oks_file']}"]
    for k, v in asdict(conf).items():
        cmd += [f"--{k.replace('_', '-')}", str(v)]

    subprocess.run(cmd, check=True, text=True)


def run_daphne_config_if_needed(cfg: dict[str, Any], *, conf_path: Path, mode: str) -> None:
    """Skip daphne configuration when requested."""
    if cfg.get("skip_daphne_conf"):
        logging.info("  Skipping daphne configuration (skip_daphne_conf=True)...")
        return
    run_daphne_config(conf_path=conf_path, mode=mode)


def ensure_details_file(details_file: Path, baseline: dict[str, Any]) -> None:
    """Make sure the temp details file exists before patching."""
    if not details_file.exists():
        details_file.write_text(pretty_compact_json(baseline))


def update_details_and_daphne(
    cfg: dict[str, Any],
    *,
    details_file: Path,
    baseline: dict[str, Any],
    update_fn: Callable[[Path, int], None],
    value: int,
    conf_file: Path,
) -> None:
    """Common sequence: ensure details file, apply patch, regenerate daphne config."""
    ensure_details_file(details_file, baseline)
    update_fn(details_file, value)
    run_daphne_config_if_needed(cfg, conf_path=conf_file, mode=cfg["mode"])


def run_ssp_and_drunc(
    cfg: dict[str, Any],
    *,
    mask: int,
    bias: int,
    delay_s: int,
) -> None:
    """Configure SSP and run drunc once."""
    run_set_ssp_conf(cfg, channel_mask=mask, pulse_bias_percent_270nm=bias)
    run_drunc_command(cfg, post_delay_s=delay_s)

def _update_correlation_threshold(details_file: Path, value: int) -> None:
    """
    Over-write *details_file*, setting
        devices[*].self_trigger.self_trigger_xcorr.correlation_threshold = value
    """
    data = json.loads(details_file.read_text())
    for dev in data.get("devices", []):
        xcorr = dev.setdefault("self_trigger", {}).setdefault(
            "self_trigger_xcorr", {}
        )
        xcorr["correlation_threshold"] = value
    details_file.write_text(pretty_compact_json(data))


def _update_self_trigger_threshold(details_file: Path, value: int) -> None:
    """
    Over-write *details_file*, setting
        devices[*].self_trigger.threshold = value
    """
    data = json.loads(details_file.read_text())
    for dev in data.get("devices", []):
        trigger = dev.setdefault("self_trigger", {})
        trigger["threshold"] = value
    details_file.write_text(pretty_compact_json(data))


def _update_attenuators(details_file: Path, value: int) -> None:
    """
    Over-write *details_file*, setting
        devices[*].channels.attenuators = [value]
    """
    data = json.loads(details_file.read_text())
    for dev in data.get("devices", []):
        att = dev.setdefault("channels", {})
        # Get the number of devices by indices
        ndevices = len(att.get('attenuators', list(range(5))))
        att["attenuators"] = [ value for _ in range(ndevices) ]
    details_file.write_text(pretty_compact_json(data))

def _update_offset(details_file: Path, value: int) -> None:
    """
    Over-write *details_file*, setting
        devices[*].channels.offsets = [values]
    """
    data = json.loads(details_file.read_text())
    for dev in data.get("devices", []):
        att = dev.setdefault("channels", {})
        # Get the number of devices by indices
        ndevices = len(att.get('offsets', list(range(16))))
        att["offsets"] = [ value for _ in range(ndevices) ]
    details_file.write_text(pretty_compact_json(data))

def _update_trim(details_file: Path, value: int) -> None:
    """
    Over-write *details_file*, setting
        devices[*].channels.trim = [values]
    """
    data = json.loads(details_file.read_text())
    for dev in data.get("devices", []):
        att = dev.setdefault("channels", {})
        # Get the number of devices by indices
        ndevices = len(att.get('trim', list(range(16))))
        bias_applied = att.get('bias')
        if all(b==0 for b in bias_applied):
            continue
        att["trim"] = [ value for _ in range(ndevices) ]
    details_file.write_text(pretty_compact_json(data))

def _retrieve_mask_intensities(cfg: dict[str, Any]) -> dict[int, list[int]]:
    """
    Read the `dailycalib` field in the json file and returns a dictionary in
    which the keys are masks and values are list of intensities.
    """
    dailycalib = cfg.get("dailycalib", [])
    if not dailycalib:
        raise ValueError("No 'dailycalib' field found in the configuration.")
    if not isinstance(dailycalib, list):
        raise ValueError("'dailycalib' should be a list of dictionaries.")
    dictret = {}
    for groups in dailycalib:
        mask = groups.get("mask", -1)
        if mask == -1:
            continue
        intensities = groups.get("intensities", [])
        if isinstance(intensities, int):
            intensities = [intensities]

        dictret[mask] = intensities
        
    return dictret
        






# ──────────────────────────────────────────────────────────────────────────────
# Main scan / single-run controller
# ──────────────────────────────────────────────────────────────────────────────
class ScanMaskIntensity:
    def __init__(self, cfg: dict[str, Any]) -> None:
        self.cfg       = cfg
        self.masks     = cfg.get("mask_values", [1])
        self.delay_s   = cfg.get("drunc_delay_s", 20)
        self.mode      = cfg.get("mode")

        self.min_bias  = cfg.get("min_bias", 4000)
        self.max_bias  = cfg.get("max_bias", 4000)
        self.step      = cfg.get("step", 500)
        self.ledrange = setup_led_range(self.min_bias, self.max_bias, self.step)
        self.pulse_width_ticks = int(cfg.get("ssp_conf", {}).get("pulse1_width_ticks", "1"))


    def run(self) -> None:
        if self.mode == "ledrun":
            logging.info("📢  Calibration: scanning masks × intensities …")
            for mask in self.masks:
                for bias in self.ledrange:
                    ledmessage = f"LED intensity = {bias}, LED width = " \
                                 f"{self.pulse_width_ticks*4} ns, mask = {mask}"
                    logging.info(ledmessage)

                    run_set_ssp_conf(self.cfg,
                                     channel_mask=mask,
                                     pulse_bias_percent_270nm=bias)
                    run_drunc_command(self.cfg, post_delay_s=self.delay_s)
            print("Scan finished... parameters done:")
            log_file = getlogfile()
            nruns = len(self.masks)*len(self.ledrange)
            if Path(log_file).is_file():
                subprocess.run(f"cat {log_file} | grep 'LED width =' | tail -n {nruns}", shell=True)
            return
        elif self.mode == "calibrun":
            logging.info("📢  Calibration: mask and intensities defined in 'dailycalib'...")
            dict_masks_intensities = _retrieve_mask_intensities(self.cfg)

            nruns = 0
            for mask, ledrange in dict_masks_intensities.items():
                for bias in ledrange:
                    ledmessage = f"LED intensity = {bias}, LED width = " \
                        f"{self.pulse_width_ticks*4} ns, mask = {mask}"
                    logging.info(ledmessage)

                    run_set_ssp_conf(self.cfg,
                                     channel_mask=mask,
                                     pulse_bias_percent_270nm=bias)
                    run_drunc_command(self.cfg, post_delay_s=self.delay_s)
                    nruns+=1
            print("Calibration finished... parameters done:")
            log_file = Path.home() / ".pds" / "logs" / "pds-run.log"
            if Path(log_file).is_file():
                subprocess.run(f"cat {log_file} | grep 'LED width =' | tail -n {nruns}", shell=True)
            return

        # Noise & cosmics: single run, LED OFF
        if self.mode in ("noise", "cosmics"):
            logging.info("📢  %s run – single acquisition, LED OFF.", self.mode)
            run_set_ssp_conf(self.cfg,
                             channel_mask=self.masks[0],
                             pulse_bias_percent_270nm=0)
            run_drunc_command(self.cfg, post_delay_s=self.delay_s)
            return

        if isinstance(self.min_bias, list):
            self.min_bias = self.min_bias[0]

        # Fallback for any other mode
        logging.info("📢  %s run – single acquisition, default LED ON.", self.mode)
        run_set_ssp_conf(self.cfg,
                         channel_mask=self.masks[0],
                         pulse_bias_percent_270nm=self.min_bias)
        run_drunc_command(self.cfg, post_delay_s=self.delay_s)

class ScanXCorrThreshold:
    """
    Iterate over self-trigger threshold values and take one run per value.

    The conf.json can add:
      min_self_trigger_threshold   (default: value in details.json, or 0)
      max_self_trigger_threshold   (default: value in details.json, or 0)
      self_trigger_threshold_step  (default 1)
    Legacy keys min_corr/max_corr/corr_step are accepted as fallbacks.
    """

    # ------------------------------------------------------------------ #

    def __init__(
        self,
        cfg: dict[str, Any],
        *,
        conf_file: Path,
        details_file: Path,
    ) -> None:
        self.cfg          = cfg
        self.conf_file    = conf_file     # …/conf_temp.json
        self.details_file = details_file  # …/temp_details.json

        # Accept new threshold keys first, fall back to the older corr keys
        self.min_thr = cfg.get("min_self_trigger_threshold", cfg.get("min_corr", 0))
        self.max_thr = cfg.get("max_self_trigger_threshold", cfg.get("max_corr", 0))
        self.step    = cfg.get("self_trigger_threshold_step", cfg.get("corr_step", 1))
        self.delay_s  = cfg.get("drunc_delay_s", 20)

        # Keep an untouched copy so we can re-create the JSON each loop
        self._baseline = json.loads(details_file.read_text())

    # ------------------------------------------------------------------ #

    def run(self) -> None:
        logging.info("📢  Threshold scan: %s → %s (step %s)",
                     self.min_thr, self.max_thr, self.step)

        thr_range = range(self.min_thr, self.max_thr + self.step, self.step)

        for thr in thr_range:

            logging.info(f"📢  self-trigger threshold = {thr}")

            update_details_and_daphne(
                self.cfg,
                details_file=self.details_file,
                baseline=self._baseline,
                update_fn=_update_self_trigger_threshold,
                value=thr,
                conf_file=self.conf_file,
            )

            run_ssp_and_drunc(
                self.cfg,
                mask=self.cfg.get("mask_values", [1])[0],
                bias=0,
                delay_s=self.delay_s,
            )

        print("Scan finished... parameters done:")
        log_file = getlogfile()
        nruns = len(thr_range)
        if Path(log_file).is_file():
            subprocess.run(f"cat {log_file} | grep 'self-trigger threshold =' | tail -n {nruns}", shell=True)


class ScanSelfTriggerThreshold:
    """
    Iterate over self-trigger threshold values and take one run per value.

    The conf.json can add:
      min_self_trigger_threshold   (default: value in details.json, or 0)
      max_self_trigger_threshold   (default: value in details.json, or 0)
      self_trigger_threshold_step  (default 1)
    """

    def __init__(
        self,
        cfg: dict[str, Any],
        *,
        conf_file: Path,
        details_file: Path,
    ) -> None:
        self.cfg          = cfg
        self.conf_file    = conf_file
        self.details_file = details_file

        # Keep an untouched copy so we can re-create the JSON each loop
        self._baseline = json.loads(details_file.read_text())
        baseline_threshold = self._extract_baseline_threshold(self._baseline)

        self.min_thr = cfg.get("min_self_trigger_threshold", baseline_threshold)
        self.max_thr = cfg.get("max_self_trigger_threshold", baseline_threshold)
        self.step    = cfg.get("self_trigger_threshold_step", 1)
        self.delay_s = cfg.get("drunc_delay_s", 20)

        if self.step == 0:
            raise ValueError("self_trigger_threshold_step must be non-zero.")

    @staticmethod
    def _extract_baseline_threshold(baseline: dict[str, Any]) -> int:
        for dev in baseline.get("devices", []):
            try:
                return int(dev.get("self_trigger", {}).get("threshold", 0))
            except (TypeError, ValueError):
                continue
        return 0

    def _range(self) -> range:
        # Inclusive range, supports positive or negative steps
        stop = self.max_thr + self.step
        return range(self.min_thr, stop, self.step)

    def run(self) -> None:
        logging.info("📢  Self-trigger threshold scan: %s → %s (step %s)",
                     self.min_thr, self.max_thr, self.step)

        thr_range = self._range()

        for thr in thr_range:
            logging.info(f"📢  self-trigger threshold = {thr}")

            update_details_and_daphne(
                self.cfg,
                details_file=self.details_file,
                baseline=self._baseline,
                update_fn=_update_self_trigger_threshold,
                value=thr,
                conf_file=self.conf_file,
            )

            run_ssp_and_drunc(
                self.cfg,
                mask=self.cfg.get("mask_values", [1])[0],
                bias=0,
                delay_s=self.delay_s,
            )

        print("Scan finished... parameters done:")
        log_file = getlogfile()
        nruns = len(thr_range)
        if Path(log_file).is_file():
            subprocess.run(f"cat {log_file} | grep 'self-trigger threshold =' | tail -n {nruns}", shell=True)

class ScanAttenuators:
    """
    Iterate over Attenuators values and take one run per array of values.

    The conf.json can add:
      min_att   (default 1990)
      max_att   (default 2010)
      att_step  (default 10)
    """

    # ------------------------------------------------------------------ #

    def __init__(
        self,
        cfg: dict[str, Any],
        *,
        conf_file: Path,
        details_file: Path,
    ) -> None:
        self.cfg          = cfg
        self.conf_file    = conf_file     # …/conf_temp.json
        self.details_file = details_file  # …/temp_details.json

        self.masks     = cfg.get("mask_values", [1])
        self.min_att = cfg.get("min_att", 2000)
        self.max_att = cfg.get("max_att", 2600)
        self.att_step     = cfg.get("att_step", 10)
        self.delay_s  = cfg.get("drunc_delay_s", 20)

        self.min_bias  = cfg.get("min_bias", 4000)
        self.max_bias  = cfg.get("max_bias", 4000)
        self.step      = cfg.get("step", 500)
        self.ledrange = setup_led_range(self.min_bias, self.max_bias, self.step)
        self.pulse_width_ticks = int(cfg.get("ssp_conf", {}).get("pulse1_width_ticks", "1"))

        # Keep an untouched copy so we can re-create the JSON each loop
        self._baseline = json.loads(details_file.read_text())

    # ------------------------------------------------------------------ #

    def run(self) -> None:
        logging.info("📢  Attenuators scan: %s → %s (step %s)",
                     self.min_att, self.max_att, self.att_step)

        attscanrange = range(self.min_att, self.max_att + self.att_step, self.att_step)
        for att in attscanrange:


            update_details_and_daphne(
                self.cfg,
                details_file=self.details_file,
                baseline=self._baseline,
                update_fn=_update_attenuators,
                value=att,
                conf_file=self.conf_file,
            )

            # 3) configure SSP 
            for mask in self.masks:
                for bias in self.ledrange:
                    logging.info("\tAttenuators = %s", att)
                    ledmessage = f"\tLED intensity = {bias}, LED width = " \
                                 f"{self.pulse_width_ticks*4} ns, mask = {mask}, " \
                                 f"att = {att}"
                    logging.info(ledmessage)
                    run_ssp_and_drunc(
                        self.cfg,
                        mask=mask,
                        bias=bias,
                        delay_s=self.delay_s,
                    )
        print("Scan finished... parameters done:")
        log_file = getlogfile()
        nruns = len(self.masks)*len(self.ledrange)*len(attscanrange)
        if Path(log_file).is_file():
            subprocess.run(f"cat {log_file} | grep 'LED width =' | tail -n {nruns}", shell=True)

class ScanOffsets:
    """
    Iterate over Offsets values and take one run per array of values.

    The conf.json can add:
      min_offset   (default 2000)
      max_offset   (default 2600)
      offset_step  (default 10)
    """

    # ------------------------------------------------------------------ #

    def __init__(
        self,
        cfg: dict[str, Any],
        *,
        conf_file: Path,
        details_file: Path,
    ) -> None:
        self.cfg          = cfg
        self.conf_file    = conf_file     # …/conf_temp.json
        self.details_file = details_file  # …/temp_details.json

        self.masks       = cfg.get("mask_values", [1])
        self.min_offset  = cfg.get("min_offset", 1990)
        self.max_offset  = cfg.get("max_offset", 2010)
        self.offset_step = cfg.get("offset_step", 10)
        self.delay_s     = cfg.get("drunc_delay_s", 20)

        self.min_bias  = cfg.get("min_bias", 1)
        self.max_bias  = cfg.get("max_bias", 1)
        self.step      = cfg.get("step", 50)
        self.ledrange = setup_led_range(self.min_bias, self.max_bias, self.step)
        self.pulse_width_ticks = int(cfg.get("ssp_conf", {}).get("pulse1_width_ticks", "1"))

        # Keep an untouched copy so we can re-create the JSON each loop
        self._baseline = json.loads(details_file.read_text())

    # ------------------------------------------------------------------ #

    def run(self) -> None:
        logging.info("📢  Offsetscan scan: %s → %s (step %s)",
                     self.min_offset, self.max_offset, self.offset_step)

        offsetscanrange = range(self.min_offset, self.max_offset + self.offset_step, self.offset_step)
        for offset in offsetscanrange:


            update_details_and_daphne(
                self.cfg,
                details_file=self.details_file,
                baseline=self._baseline,
                update_fn=_update_offset,
                value=offset,
                conf_file=self.conf_file,
            )

            # 3) configure SSP 
            for mask in self.masks:
                for bias in self.ledrange:
                    logging.info("\tOffset = %s", offset)
                    ledmessage = f"\tLED intensity = {bias}, LED width = " \
                                 f"{self.pulse_width_ticks*4} ns, mask = {mask}, " \
                                 f"Offset = {offset}"
                    logging.info(ledmessage)
                    run_ssp_and_drunc(
                        self.cfg,
                        mask=mask,
                        bias=bias,
                        delay_s=self.delay_s,
                    )
        print("Scan finished... parameters done:")
        log_file = getlogfile()
        nruns = len(self.masks)*len(self.ledrange)*len(offsetscanrange)
        if Path(log_file).is_file():
            subprocess.run(f"cat {log_file} | grep 'LED width =' | tail -n {nruns}", shell=True)

class ScanTrims:
    """
    Iterate over trim values and take one run per array of values.

    The conf.json can add:
      min_trim   (default 0)
      max_trim   (default 1000)
      trim_step  (default 10)
    """

    # ------------------------------------------------------------------ #

    def __init__(
        self,
        cfg: dict[str, Any],
        *,
        conf_file: Path,
        details_file: Path,
    ) -> None:
        self.cfg          = cfg
        self.conf_file    = conf_file     # …/conf_temp.json
        self.details_file = details_file  # …/temp_details.json

        self.masks       = cfg.get("mask_values", [1])
        self.min_trim  = cfg.get("min_trim", 0)
        self.max_trim  = cfg.get("max_trim", 3000)
        self.trim_step = cfg.get("trim_step", 20)
        self.delay_s     = cfg.get("drunc_delay_s", 20)

        self.min_bias  = cfg.get("min_bias", "4000")
        self.max_bias  = cfg.get("max_bias", "4000")
        self.step      = cfg.get("step", 50)
        self.ledrange = setup_led_range(self.min_bias, self.max_bias, self.step)
        self.pulse_width_ticks = int(cfg.get("ssp_conf", {}).get("pulse1_width_ticks", "1"))

        # Keep an untouched copy so we can re-create the JSON each loop
        self._baseline = json.loads(details_file.read_text())

    # ------------------------------------------------------------------ #

    def run(self) -> None:
        logging.info("📢  Offsetscan scan: %s → %s (step %s)",
                     self.min_trim, self.max_trim, self.trim_step)

        trimscanrange = range(self.min_trim, self.max_trim + self.trim_step, self.trim_step)
        for trim in trimscanrange:


            update_details_and_daphne(
                self.cfg,
                details_file=self.details_file,
                baseline=self._baseline,
                update_fn=_update_trim,
                value=trim,
                conf_file=self.conf_file,
            )

            # 3) configure SSP 
            for mask in self.masks:
                for bias in self.ledrange:
                    ledmessage = f"\tLED intensity = {bias}, LED width = " \
                                 f"{self.pulse_width_ticks*4} ns, mask = {mask}, " \
                                 f"Trim = {trim}"
                    logging.info(ledmessage)
                    run_ssp_and_drunc(
                        self.cfg,
                        mask=mask,
                        bias=bias,
                        delay_s=self.delay_s,
                    )
        print("Scan finished... parameters done:")
        log_file = getlogfile()
        nruns = len(self.masks)*len(self.ledrange)*len(trimscanrange)
        if Path(log_file).is_file():
            subprocess.run(f"cat {log_file} | grep 'LED width =' | tail -n {nruns}", shell=True)


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
            if cfg.get("skip_dts"):
                logging.info("  Skipping Butler commands (skip_dts=True)...")
            elif not cfg["dry_run"]:  # Avoid butler when dry run
                dts.run()
            else:
                logging.info("  Skipping Butler run commands...")

            WebProxy.setup(cfg)

            # ── select the proper scan type ──────────────────────────────
            mode = cfg["mode"]
            if mode in ("thrscan", "threshold"):
                # new x-corr threshold scan
                ScanXCorrThreshold(
                    cfg,
                    conf_file=temp_conf,
                    details_file=temp_detail,
                ).run()
            elif mode in ("sthscan", "selftrigger"):
                # self-trigger threshold scan
                ScanSelfTriggerThreshold(
                    cfg,
                    conf_file=temp_conf,
                    details_file=temp_detail,
                ).run()
            elif mode in ("attscan", "attenuator"):
                # new attenuator scan (always 5 channels of identical values)
                ScanAttenuators(
                    cfg,
                    conf_file=temp_conf,
                    details_file=temp_detail,
                ).run()
            elif mode == "offsetscan":
                # new offset scan (always same value)
                ScanOffsets(
                    cfg,
                    conf_file=temp_conf,
                    details_file=temp_detail,
                ).run()
            elif mode == "trimscan":
                # new trim scan (always same value)
                ScanTrims(
                    cfg,
                    conf_file=temp_conf,
                    details_file=temp_detail,
                ).run()

            else:
                # existing mask/intensity scan
                run_daphne_config_if_needed(cfg,
                                            conf_path=temp_conf,
                                            mode=mode)
                ScanMaskIntensity(cfg).run()
        finally:
            if cfg.get("skip_dts"):
                logging.info("  Skipping Butler clear commands (skip_dts=True)...")
            elif not cfg["dry_run"]:
                dts.clear()  # always attempt to clear fake trigger
            else:
                logging.info("  Skipping Butler clear commands...")


if __name__ == "__main__":  # pragma: no cover
    if len(sys.argv) < 3:
        print("Usage: python -m pds.core.run <mode> <conf.json>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
