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
        wd = cfg["drunc_working_dir"]
        self.mode = cfg.get("mode")

        self.align_cmd    = ["bash", "-c", f"cd {wd} && {cfg['dts_align_cmd']}"]
        self.fake_cmd_tpl = ["bash", "-c", f"cd {wd} && {cfg['dts_faketrig_cmd_template']}"]
        self.clear_cmd    = ["bash", "-c", f"cd {wd} && {cfg['dts_clear_fktrig_cmd']}"]

    # ------------------------------------------------------------------ #

    def run(self) -> None:
        # Skip alignment + periodic fake-triggers in cosmics *and* threshold scans
        if self.mode in ("cosmics", "thrscan", "threshold"):
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
    drunc_command = (
        "drunc-unified-shell ssh-CERN-kafka.json "
        f"{cfg['oks_session']} {cfg['session_name']} main-np02-pds "
        f"start-run --run-type {cfg['storage_type']} change-rate --trigger-rate "
        f"{cfg['change_rate']} wait {cfg['wait_time']} "
        "shutdown terminate"
        )
    if cfg.get("dry_run"):

        return (
        "echo '🧪 [dry-run] Simulating drunc command...:'\n" + drunc_command
        )
    return (
        drunc_command
    )

def generate_drunc_boot(cfg: dict[str, Any]) -> str:
    drunc_command = (
        "drunc-unified-shell ssh-CERN-kafka.json "
        f"{cfg['oks_session']} {cfg['session_name']} main-np02-pds "
        "boot conf scrap "
        "shutdown terminate"
        )
    if cfg.get("dry_run"):
        return (
        "echo '🧪 [dry-run] Simulating drunc command for boot...:'\n" + drunc_command
        )
    return (
        drunc_command
    )

def run_drunc_command(cfg: dict[str, Any], *, post_delay_s: int = 20) -> None:
    cmd_boot = generate_drunc_boot(cfg)
    cmd = generate_drunc_command(cfg)
    if cfg.get("dry_run"):
        logging.info("🧪 Dry run: %s", cmd)
        return
    logging.info(f"{cmd}")

    verify_boot = cfg.get('verify_boot', False)
    
    output = ""
    if verify_boot:
        logging.info("Executing a drunc command with boot only to check if there is an error")
        result = subprocess.run(cmd_boot, shell=True, cwd=cfg["drunc_working_dir"], capture_output=True, text=True)
        output = result.stdout
        if "ERROR" in output:
            # Executing again so user has a nice display of what is happening
            logging.info("Boot fail, doing it again so user can follow")
            subprocess.run(cmd_boot, shell=True, cwd=cfg["drunc_working_dir"]) 
            logging.error("There was an error while booting... stopping (If there was no error now, just try again)")
            exit(1)
        logging.info("Done")

    subprocess.run(cmd, shell=True, cwd=cfg["drunc_working_dir"], check=True)
    
    print(f"Sleeping for {post_delay_s} seconds. Press Ctrl+C if you need to stop...")
    try:
        time.sleep(post_delay_s)
    except KeyboardInterrupt:
        print("\nScript interrupted by user.")
        exit(0)

    print("Continuing execution...")

def run_set_ssp_conf(cfg: dict[str, Any], **overrides: Any) -> None:
    conf = SSPConf.from_config(cfg)
    for k, v in overrides.items():
        if v is not None and hasattr(conf, k):
            setattr(conf, k, v)

    if conf.pulse_bias_percent_270nm == 0 or conf.pulse_bias_percent_367nm == 0:
        logging.warning(
            f"\n\t\t\t\tpulse_bias_percent_270nm: {conf.pulse_bias_percent_270nm}"
            f"\n\t\t\t\tpulse_bias_percent_367nm: {conf.pulse_bias_percent_367nm}"
            f"\n\t\t\t\tIf pulse_bias_percent is set to zero, the previous configuration is used"
        )
        time.sleep(2)

    cmd = ["set_ssp_conf", f"{cfg['drunc_working_dir']}/{cfg['oks_file']}"]
    for k, v in asdict(conf).items():
        cmd += [f"--{k.replace('_', '-')}", str(v)]

    if cfg['dry_run']:
        logging.info("🧪 Dry run, skipping SSP: %s", ' '.join(cmd))
        return
    subprocess.run(cmd, check=True, text=True)

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

                    overrides = { "channel_mask": mask }
                    biasAt270nm = int(self.cfg.get("ssp_conf", {}).get("pulse_bias_percent_270nm", "1"))
                    biasAt367nm = int(self.cfg.get("ssp_conf", {}).get("pulse_bias_percent_367nm", "1"))
                    biascontrol = "pulse_bias_percent_270nm"
                    if biasAt270nm > 1 and biasAt367nm > 1:
                        raise ValueError("Only one scan at a time. Set either pulse_bias_percent_270nm or pulse_bias_percent_367nm to 0.")
                    elif biasAt367nm > 1:
                        biascontrol = "pulse_bias_percent_367nm"
                    elif biasAt270nm > 1:
                        biascontrol = "pulse_bias_percent_270nm"
                    else:
                        raise ValueError("Set one default number (pulse_bias_percent_270nm or pulse_bias_percent_367nm) higher than 1 and the other one to 1.")

                    overrides[biascontrol] = bias
                    run_set_ssp_conf(self.cfg, **overrides)

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
                             pulse_bias_percent_270nm=1,
                             pulse_bias_percent_367nm=1)
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
    Iterate over correlation-threshold (xcorr) values and take one run per value.

    The conf.json can add:
      min_corr   (default 4000)
      max_corr   (default 8000)
      corr_step  (default 500)
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

        self.min_corr = cfg.get("min_corr", 4000)
        self.max_corr = cfg.get("max_corr", 8000)
        self.step     = cfg.get("corr_step", 500)
        self.delay_s  = cfg.get("drunc_delay_s", 20)

        # Keep an untouched copy so we can re-create the JSON each loop
        self._baseline = json.loads(details_file.read_text())

    # ------------------------------------------------------------------ #

    def run(self) -> None:
        logging.info("📢  Threshold scan: %s → %s (step %s)",
                     self.min_corr, self.max_corr, self.step)
        
        xcorrrange = range(self.min_corr, self.max_corr + self.step, self.step)

        for corr in xcorrrange:

            logging.info(f"📢  xcorr = {corr}")

            # 1) make sure temp_details.json exists, then patch it
            if not self.details_file.exists():
                self.details_file.write_text(pretty_compact_json(self._baseline))
            _update_correlation_threshold(self.details_file, corr)

            # 2) regenerate seeds + XML for the new threshold
            run_daphne_config(conf_path=self.conf_file, mode=self.cfg["mode"])

            # 3) configure SSP *with LED OFF* (bias = 0) like cosmics
            run_set_ssp_conf(
                self.cfg,
                channel_mask=self.cfg.get("mask_values", [1])[0],
                pulse_bias_percent_270nm=1,
                pulse_bias_percent_367nm=1
            )

            # 4) run drunc acquisition
            run_drunc_command(self.cfg, post_delay_s=self.delay_s)

        print("Scan finished... parameters done:")
        log_file = getlogfile()
        nruns = len(xcorrrange)
        if Path(log_file).is_file():
            subprocess.run(f"cat {log_file} | grep 'xcorr = ' | tail -n {nruns}", shell=True)

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


            # 1) make sure temp_details.json exists, then patch it
            if not self.details_file.exists():
                self.details_file.write_text(pretty_compact_json(self._baseline))
            _update_attenuators(self.details_file, att)

            # 2) regenerate seeds + XML for the new threshold
            run_daphne_config(conf_path=self.conf_file, mode=self.cfg["mode"])

            # 3) configure SSP 
            for mask in self.masks:
                for bias in self.ledrange:
                    logging.info("\tAttenuators = %s", att)
                    ledmessage = f"\tLED intensity = {bias}, LED width = " \
                                 f"{self.pulse_width_ticks*4} ns, mask = {mask}, " \
                                 f"att = {att}"
                    logging.info(ledmessage)
                    run_set_ssp_conf(self.cfg,
                                     channel_mask=mask,
                                     pulse_bias_percent_270nm=bias)
                    # 4) run drunc acquisition
                    run_drunc_command(self.cfg, post_delay_s=self.delay_s)
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


            # 1) make sure temp_details.json exists, then patch it
            if not self.details_file.exists():
                self.details_file.write_text(pretty_compact_json(self._baseline))
            #
            _update_offset(self.details_file, offset)

            # 2) regenerate seeds + XML for the new threshold
            run_daphne_config(conf_path=self.conf_file, mode=self.cfg["mode"])

            # 3) configure SSP 
            for mask in self.masks:
                for bias in self.ledrange:
                    logging.info("\tOffset = %s", offset)
                    ledmessage = f"\tLED intensity = {bias}, LED width = " \
                                 f"{self.pulse_width_ticks*4} ns, mask = {mask}, " \
                                 f"Offset = {offset}"
                    logging.info(ledmessage)
                    run_set_ssp_conf(self.cfg,
                                     channel_mask=mask,
                                     pulse_bias_percent_270nm=bias)
                    # 4) run drunc acquisition
                    run_drunc_command(self.cfg, post_delay_s=self.delay_s)
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


            # 1) make sure temp_details.json exists, then patch it
            if not self.details_file.exists():
                self.details_file.write_text(pretty_compact_json(self._baseline))
            #
            _update_trim(self.details_file, trim)

            # 2) regenerate seeds + XML for the new threshold
            run_daphne_config(conf_path=self.conf_file, mode=self.cfg["mode"])

            # 3) configure SSP 
            for mask in self.masks:
                for bias in self.ledrange:
                    ledmessage = f"\tLED intensity = {bias}, LED width = " \
                                 f"{self.pulse_width_ticks*4} ns, mask = {mask}, " \
                                 f"Trim = {trim}"
                    logging.info(ledmessage)
                    run_set_ssp_conf(self.cfg,
                                     channel_mask=mask,
                                     pulse_bias_percent_270nm=bias)
                    # 4) run drunc acquisition
                    run_drunc_command(self.cfg, post_delay_s=self.delay_s)
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
            if not cfg["dry_run"]: # Avoid butler when dry run
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
                run_daphne_config(conf_path=temp_conf, mode=mode)
                ScanMaskIntensity(cfg).run()
        finally:
            if not cfg["dry_run"]:
                dts.clear()  # always attempt to clear fake trigger
            else:
                logging.info("  Skipping Butler clear commands...")


if __name__ == "__main__":  # pragma: no cover
    if len(sys.argv) < 3:
        print("Usage: python -m pds.core.run <mode> <conf.json>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])

