#!/usr/bin/env python3

import subprocess
import sys
import argparse
import json
import time

# ANSI escape codes for colors
GREEN = "\033[92m"   # Success
YELLOW = "\033[93m"  # Warnings / Start messages
RED = "\033[91m"     # Errors
BLUE = "\033[94m"    # Information
RESET = "\033[0m"    # Reset color


# ------------------------------------------------------------------------------
# CLASSES
# ------------------------------------------------------------------------------

class WebProxy:
    """Handles sourcing the web proxy at the beginning of execution."""

    @staticmethod
    def setup(config):
        """Sources the web proxy script from JSON configuration, unless skipped."""
        if config.get("skip_proxy", False):
            print(f"{YELLOW}⚠️ Skipping Web Proxy setup (skip_proxy=True).{RESET}")
            return

        web_proxy_cmd = f"cd {config['drunc_working_dir']} && {config['web_proxy_cmd']}"
        print(f"{YELLOW}📢 Sourcing web proxy...{RESET}")
        result = subprocess.call(f"bash -c '{web_proxy_cmd}'", shell=True)
        if result != 0:
            print(f"{RED}❌ Error: Failed to source web_proxy.sh{RESET}")
            sys.exit(1)
        print(f"{GREEN}✅ Web proxy sourced successfully.{RESET}")


class DTSButler:
    """Handles the execution of DTS commands (alignment and fake triggers)."""

    def __init__(self, config):
        self.hztrigger = config["hztrigger"]
        workdir = config["drunc_working_dir"]
        self.skip_dts = config.get("skip_dts", False)

        self.dts_align_cmd = f"cd {workdir} && {config['dts_align_cmd']}"
        self.dts_faketrig_cmd_template = f"cd {workdir} && {config['dts_faketrig_cmd_template']}"

    def run(self):
        """Runs DTS alignment and fake trigger configuration, unless skipped."""
        if self.skip_dts:
            print(f"{YELLOW}⚠️ Skipping DTS alignment & fake trigger (skip_dts=True).{RESET}")
            return

        print(f"{YELLOW}📢 Running DTS alignment...{RESET}")
        if subprocess.call(self.dts_align_cmd, shell=True) != 0:
            print(f"{RED}❌ Error: DTS alignment command failed.{RESET}")
            sys.exit(1)
        print(f"{GREEN}✅ DTS alignment completed.{RESET}")

        dts_faketrig_cmd = self.dts_faketrig_cmd_template.format(hztrigger=self.hztrigger)
        print(f"{YELLOW}📢 Configuring DTS fake trigger...{RESET}")
        if subprocess.call(dts_faketrig_cmd, shell=True) != 0:
            print(f"{RED}❌ Error: DTS fake trigger command failed.{RESET}")
            sys.exit(1)
        print(f"{GREEN}✅ DTS fake trigger configured.{RESET}")


# ------------------------------------------------------------------------------
# HELPER FUNCTIONS
# ------------------------------------------------------------------------------

def run_daphne_config(config, config_path):
    """
    Executes set_daphne_conf.py using parameters from 'config' plus your JSON file path.
    """
    # We pass the JSON config path as an argument to the python script
    cmd = [
        sys.executable,
        f"{config['drunc_working_dir']}/pds/scripts/daq_acquisition/np02/set_daphne_conf.py",
        config_path
    ]

    print(f"{YELLOW}📢 Running set_daphne_conf.py...{RESET}")
    if subprocess.call(cmd) != 0:
        print(f"{RED}❌ Error: set_daphne_conf.py command failed.{RESET}")
        sys.exit(1)
    print(f"{GREEN}✅ Daphne configuration completed.{RESET}")


def generate_drunc_command(config):
    """
    Generates the drunc-unified-shell command dynamically using values from the config.
    Adjust the final steps or commands as needed.
    """
    return (
        f"drunc-unified-shell ssh-standalone "
        f"{config['oks_session']} {config['session_name']} np02-pds "
        f"boot conf start enable-triggers change-rate --trigger-rate {config['change_rate']} wait {config['wait_time']} "
        f"disable-triggers drain-dataflow stop-trigger-sources stop terminate"
    )


def run_drunc_command(config, post_delay_s=20):
    """
    Runs the drunc-unified-shell command with dynamic parameters,
    then sleeps for 'post_delay_s' seconds to let it finish cleaning up.
    """
    drunc_cmd = generate_drunc_command(config)
    drunc_working_dir = config["drunc_working_dir"]

    print(f"{YELLOW}📢 Running drunc-unified-shell from {drunc_working_dir}...{RESET}")
    print(f"{BLUE}{drunc_cmd}{RESET}")

    if subprocess.call(drunc_cmd, shell=True, cwd=drunc_working_dir) != 0:
        print(f"{RED}❌ Error: drunc-unified-shell command failed.{RESET}")
        sys.exit(1)

    print(f"{GREEN}✅ drunc-unified-shell completed successfully.{RESET}")

    # Sleep so drunc can fully shut down before next iteration
    time.sleep(post_delay_s)


def run_set_ssp_conf(config, **kwargs):
    """
    Runs set_ssp_conf using:
      - Hardcoded defaults
      - Overridden by config['ssp_conf'] (if present)
      - Overridden by function kwargs
    """
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
        if key in [
            "channel_mask", "number_channels", "burst_count",
            "double_pulse_delay_ticks", "pulse1_width_ticks",
            "pulse2_width_ticks", "pulse_bias_percent_270nm",
            "pulse_bias_percent_367nm"
        ]:
            ssp_defaults[key] = int(val)
        else:
            ssp_defaults[key] = val

    for key, val in kwargs.items():
        if val is not None:
            ssp_defaults[key] = val

    # Build final command
    oks_file = f"{config['drunc_working_dir']}/{config['oks_file']}"
    cmd = ["set_ssp_conf", oks_file]
    for key, val in ssp_defaults.items():
        option = f"--{key.replace('_', '-')}"
        cmd.append(option)
        cmd.append(str(val))

    print(f"{YELLOW}📢 Running set_ssp_conf...{RESET}")
    print(f"{BLUE}{cmd}{RESET}")
    try:
        result = subprocess.run(cmd, check=True, text=True, capture_output=True)
        print(f"{GREEN}✅ set_ssp_conf executed successfully.{RESET}")
        if result.stdout:
            print(f"{BLUE}Output:\n{result.stdout}{RESET}")
    except subprocess.CalledProcessError as e:
        print(f"{RED}❌ Error running set_ssp_conf:{RESET}")
        print(f"{RED}stderr: {e.stderr}{RESET}")
        sys.exit(1)


class ScanMaskIntensity:
    """
    Iterates over both 'channel_mask' and 'pulse_bias_percent_270nm' values,
    calling run_set_ssp_conf() then run_drunc_command() each time.
    """

    def __init__(self, config):
        self.config = config
        self.mask_values = config.get("mask_values", [1])
        self.min_bias = config.get("min_bias", 4000)
        self.max_bias = config.get("max_bias", 4000)
        self.step = config.get("step", 500)
        self.drunc_delay_s = config.get("drunc_delay_s", 20)

    def run(self):
        print(f"{YELLOW}📢 Starting SCAN MASK & INTENSITY TEST...{RESET}")
        for mask in self.mask_values:
            for bias in range(self.min_bias, self.max_bias + self.step, self.step):
                run_set_ssp_conf(
                    self.config,
                    channel_mask=mask,
                    pulse_bias_percent_270nm=bias
                )
                run_drunc_command(self.config, post_delay_s=self.drunc_delay_s)


# ------------------------------------------------------------------------------
# MAIN
# ------------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run configuration script using JSON input.")
    parser.add_argument("--config", required=True, help="Path to the configuration JSON file.")
    args = parser.parse_args()

    # Load the config from JSON
    with open(args.config, "r") as file:
        config = json.load(file)

    # 1) DTS Setup (skip if 'skip_dts': true)
    dtsbutler = DTSButler(config)
    dtsbutler.run()

    # 2) Web Proxy Setup (skip if 'skip_proxy': true)
    WebProxy.setup(config)

    # 3) Daphne config
    run_daphne_config(config, args.config)

    # 4) The scanning test
    scan_test = ScanMaskIntensity(config)
    scan_test.run()