import logging
import subprocess
import sys
import json
import time
import os
from pathlib import Path
from pds.core.set_daphne_conf import main as run_daphne_config

# ------------------------------------------------------------------------------
# CLASSES
# ------------------------------------------------------------------------------

class WebProxy:
    @staticmethod
    def setup(config):
        if config.get("skip_proxy", False):
            logging.warning("⚠️ Skipping Web Proxy setup (skip_proxy=True).")
            return

        web_proxy_cmd = f"cd {config['drunc_working_dir']} && {config['web_proxy_cmd']}"
        logging.info("📢 Sourcing web proxy...")
        result = subprocess.call(f"bash -c '{web_proxy_cmd}'", shell=True)
        if result != 0:
            logging.error("❌ Error: Failed to source web_proxy.sh")
            sys.exit(1)
        logging.info("✅ Web proxy sourced successfully.")

class DTSButler:
    def __init__(self, config):
        self.hztrigger = config["hztrigger"]
        workdir = config["drunc_working_dir"]
        self.mode = config.get("mode")

        self.dts_align_cmd = f"cd {workdir} && {config['dts_align_cmd']}"
        self.dts_faketrig_cmd_template = f"cd {workdir} && {config['dts_faketrig_cmd_template']}"
        self.dts_clear_fktrig_cmd = f"cd {workdir} && {config['dts_clear_fktrig_cmd']}"

    def run(self):
        if self.mode == "cosmics":
            logging.warning("⚠️ Skipping DTS alignment & clearing ad-hoc trigger.")
            self.clear()
            return

        logging.info("📢 Running DTS alignment...")
        if subprocess.call(self.dts_align_cmd, shell=True) != 0:
            logging.error("❌ Error: DTS alignment command failed.")
            sys.exit(1)
        logging.info("✅ DTS alignment completed.")

        dts_faketrig_cmd = self.dts_faketrig_cmd_template.format(hztrigger=self.hztrigger)
        logging.info("📢 Configuring DTS fake trigger...")
        if subprocess.call(dts_faketrig_cmd, shell=True) != 0:
            logging.error("❌ Error: DTS fake trigger command failed.")
            sys.exit(1)
        logging.info("✅ DTS fake trigger configured.")

    def clear(self):
        """Always try to clear DTS fake triggers."""
        logging.info("📢 Clearing DTS fake trigger at the end of run...")
        if subprocess.call(self.dts_clear_fktrig_cmd, shell=True) != 0:
            logging.error("❌ Failed to clear DTS fake trigger.")
        else:
            logging.info("✅ DTS fake trigger cleared.")

# ------------------------------------------------------------------------------
# HELPER FUNCTIONS
# ------------------------------------------------------------------------------

def update_temp_details(details_path, temp_details_path, mode):
    with open(details_path, 'r') as f:
        details = json.load(f)

    for device in details.get("devices", []):
        if mode == "cosmics":
            device.setdefault("self_trigger", {})["self_trigger_xcorr"] = {
                "correlation_threshold": 4000,
                "discrimination_threshold": 5000
            }
        elif mode in ("noise", "calibration"):
            device.setdefault("self_trigger", {})["self_trigger_xcorr"] = {
                "correlation_threshold": 268435455,
                "discrimination_threshold": 10
            }

    with open(temp_details_path, 'w') as f:
        json.dump(details, f, indent=2)

    logging.info(f"✅ Generated modified temp details file: {temp_details_path}")


def generate_drunc_command(config):
    return (
        f"drunc-unified-shell ssh-standalone "
        f"{config['oks_session']} {config['session_name']} np02-pds "
        f"boot conf start enable-triggers change-rate --trigger-rate {config['change_rate']} wait {config['wait_time']} "
        f"disable-triggers drain-dataflow stop-trigger-sources stop scrap terminate"
    )

def run_drunc_command(config, post_delay_s=20):
    drunc_cmd = generate_drunc_command(config)
    drunc_working_dir = config["drunc_working_dir"]

    logging.info(f"📢 Running drunc-unified-shell from {drunc_working_dir}...")
    logging.info(f"Command: {drunc_cmd}")

    if subprocess.call(drunc_cmd, shell=True, cwd=drunc_working_dir) != 0:
        logging.error("❌ Error: drunc-unified-shell command failed.")
        sys.exit(1)

    logging.info("✅ drunc-unified-shell completed successfully.")
    time.sleep(post_delay_s)

def run_set_ssp_conf(config, **kwargs):
    ssp_defaults = {
        "object_name": "np02-ssp-on",
        "number_channels": 12,
        "channel_mask": 1,
        "pulse_mode": "single",
        "burst_count": 1,
        "double_pulse_delay_ticks": 0,
        "pulse1_width_ticks": 5,
        "pulse2_width_ticks": 0,
        "pulse_bias_percent_270nm": 4000,
        "pulse_bias_percent_367nm": 0
    }

    user_conf = config.get("ssp_conf", {})
    for key, val in user_conf.items():
        if key in ssp_defaults:
            ssp_defaults[key] = int(val) if isinstance(val, str) and val.isdigit() else val

    for key, val in kwargs.items():
        if val is not None:
            ssp_defaults[key] = val

    oks_file = f"{config['drunc_working_dir']}/{config['oks_file']}"
    cmd = ["set_ssp_conf", oks_file]
    for key, val in ssp_defaults.items():
        option = f"--{key.replace('_', '-')}"
        cmd.append(option)
        cmd.append(str(val))

    logging.info(f"📢 Running set_ssp_conf: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, check=True, text=True, capture_output=True)
        logging.info(f"✅ set_ssp_conf executed successfully. Output:\n{result.stdout}")
    except subprocess.CalledProcessError as e:
        logging.error(f"❌ Error running set_ssp_conf: {e.stderr}")
        sys.exit(1)

class ScanMaskIntensity:
    def __init__(self, config):
        self.config = config
        self.mask_values = config.get("mask_values", [1])
        self.min_bias = config.get("min_bias", 4000)
        self.max_bias = config.get("max_bias", 4000)
        self.step = config.get("step", 500)
        self.drunc_delay_s = config.get("drunc_delay_s", 20)
        self.mode = config.get("mode")

    def run(self):
        if self.mode == "noise":
            logging.info("📢 Noise run LED OFF...")
            run_set_ssp_conf(self.config, pulse_bias_percent_270nm=0)
            run_drunc_command(self.config, post_delay_s=self.drunc_delay_s)
        else:
            logging.info("📢 Starting SCAN MASK & INTENSITY TEST...")
            for mask in self.mask_values:
                for bias in range(self.min_bias, self.max_bias + self.step, self.step):
                    run_set_ssp_conf(self.config, channel_mask=mask, pulse_bias_percent_270nm=bias)
                    run_drunc_command(self.config, post_delay_s=self.drunc_delay_s)

# ------------------------------------------------------------------------------
# MAIN
# ------------------------------------------------------------------------------


def main(mode=None, conf_path=None):
    if conf_path is None:
        logging.error("Configuration path must be provided.")
        raise ValueError("Configuration path is required.")

    conf_path = Path(conf_path)
    if not conf_path.exists():
        raise FileNotFoundError(f"Configuration file does not exist at {conf_path}")

    with open(conf_path, "r") as file:
        original_config = json.load(file)

    config_for_run = original_config.copy()

    temp_conf_path = conf_path.parent / "conf_temp.json"
    temp_details_path = None
    dtsbutler = None

    try:
        if mode is not None:
            config_for_run["mode"] = mode

            # Create temp details.json exactly in the same folder as conf.json
            details_path = conf_path.parent / Path(original_config["daphne_details"]).name
            temp_details_path = conf_path.parent / "temp_details.json"

            update_temp_details(details_path, temp_details_path, mode)
            drunc_dir = Path(original_config["drunc_working_dir"]).resolve()
            relative_temp_details = temp_details_path.resolve().relative_to(drunc_dir)
            config_for_run["daphne_details"] = str(relative_temp_details)
        # Create temp conf
        with open(temp_conf_path, "w") as f:
            json.dump(config_for_run, f, indent=2)

        logging.info(f"✅ Created temp conf file: {temp_conf_path}")

        dtsbutler = DTSButler(config_for_run)
        dtsbutler.run()

        WebProxy.setup(config_for_run)

        run_daphne_config(conf_path=temp_conf_path)

        scan_test = ScanMaskIntensity(config_for_run)
        scan_test.run()

    finally:
        if dtsbutler is not None:
            dtsbutler.clear()

        if temp_conf_path.exists():
            logging.info(f"🧹 Cleaning up temporary config file: {temp_conf_path}")
            os.remove(temp_conf_path)
        if temp_details_path and temp_details_path.exists():
            logging.info(f"🧹 Cleaning up temporary details file: {temp_details_path}")
            os.remove(temp_details_path)

if __name__ == "__main__":
    main()
