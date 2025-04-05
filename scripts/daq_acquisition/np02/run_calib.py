#!/usr/bin/env python3

import subprocess
import sys
import argparse
import json

# ANSI escape codes for colors
GREEN = "\033[92m"  # Success
YELLOW = "\033[93m"  # Warnings / Start messages
RED = "\033[91m"  # Errors
BLUE = "\033[94m"  # Information
RESET = "\033[0m"  # Reset color

class WebProxy:
    """Handles sourcing the web proxy at the beginning of execution."""

    @staticmethod
    def setup(config):
        """Sources the web proxy script from JSON configuration."""
        web_proxy_cmd = f"cd {config['drunc_working_dir']} && {config['web_proxy_cmd']}"
        print(f"{YELLOW}📢 Sourcing web proxy...{RESET}")
        result = subprocess.call(f"bash -c '{web_proxy_cmd}'", shell=True)
        if result != 0:
            print(f"{RED}❌ Error: Failed to source web_proxy.sh{RESET}")
            sys.exit(1)
        print(f"{GREEN}✅ Web proxy sourced successfully.{RESET}")

class DTSButler:
    """Handles the execution of DTS commands."""

    def __init__(self, config):
        self.hztrigger = config["hztrigger"]
        self.dts_align_cmd = f"cd {config['drunc_working_dir']} && {config['dts_align_cmd']}"
        self.dts_faketrig_cmd_template = (
            f"cd {config['drunc_working_dir']} && {config['dts_faketrig_cmd_template']}"
        )

    def run(self):
        """Runs DTS alignment and fake trigger configuration."""
        print(f"{YELLOW}📢 Running DTS alignment...{RESET}")
        result = subprocess.call(self.dts_align_cmd, shell=True)
        if result != 0:
            print(f"{RED}❌ Error: DTS alignment command failed.{RESET}")
            sys.exit(1)
        print(f"{GREEN}✅ DTS alignment completed.{RESET}")

        dts_faketrig_cmd = self.dts_faketrig_cmd_template.format(hztrigger=self.hztrigger)
        print(f"{YELLOW}📢 Configuring DTS fake trigger...{RESET}")
        result = subprocess.call(dts_faketrig_cmd, shell=True)
        if result != 0:
            print(f"{RED}❌ Error: DTS fake trigger command failed.{RESET}")
            sys.exit(1)
        print(f"{GREEN}✅ DTS fake trigger configured.{RESET}")

def run_daphne_config(config):
    """Executes set_daphne_conf.py using parameters from the config dictionary."""
    cmd = [
        sys.executable,
        f"{config['drunc_working_dir']}/pds/scripts/daq_acquisition/np02/set_daphne_conf.py",
        args.config  
    ]

    print(f"{YELLOW}📢 Running set_daphne_conf.py...{RESET}")
    result = subprocess.call(cmd)

    if result != 0:
        print(f"{RED}❌ Error: set_daphne_conf.py command failed.{RESET}")
        sys.exit(1)
    print(f"{GREEN}✅ Daphne configuration completed.{RESET}")

def generate_drunc_command(config):
    """Generates the drunc-unified-shell command dynamically using values from the config."""
    return (
        f"drunc-unified-shell ssh-standalone "
        f"{config['oks_session']} {config['session_name']} manu-test-np02 "
        f"boot conf start enable-triggers change-rate --trigger-rate {config['change_rate']} wait {config['wait_time']} "
        f"disable-triggers drain-dataflow stop-trigger-sources stop scrap terminate"
    )

def run_drunc_command(config):
    """Runs the drunc-unified-shell command with dynamic parameters."""
    drunc_cmd = generate_drunc_command(config)
    drunc_working_dir = config["drunc_working_dir"]

    print(f"{YELLOW}📢 Running drunc-unified-shell from {drunc_working_dir}...{RESET}")
    print(f"{BLUE}{drunc_cmd}{RESET}")
    result = subprocess.call(drunc_cmd, shell=True, cwd=drunc_working_dir)

    if result != 0:
        print(f"{RED}❌ Error: drunc-unified-shell command failed.{RESET}")
        sys.exit(1)
    print(f"{GREEN}✅ drunc-unified-shell completed successfully.{RESET}")

def run_set_ssp_conf(config, **kwargs):
    """
    Runs set_ssp_conf using:
      - Hardcoded defaults in code
      - Overridden by config['ssp_conf'] dictionary if present
      - Overridden by function kwargs (like channel_mask, etc.)
    """
    # 1) Our code defaults
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

    # 2) Overwrite defaults with any fields from config["ssp_conf"]
    user_conf = config.get("ssp_conf", {})
    for key, val in user_conf.items():
        # if user_conf["channel_mask"] is "8", we might parse to int
        # or keep string if set_ssp_conf expects str. Let's parse int for numeric fields:
        if key in ["channel_mask", "number_channels",
                    "burst_count", "double_pulse_delay_ticks",
                    "pulse1_width_ticks", "pulse2_width_ticks",
                    "pulse_bias_percent_270nm", "pulse_bias_percent_367nm"]:
            ssp_defaults[key] = int(val)
        else:
            ssp_defaults[key] = val

    # 3) Overwrite again with any function kwargs
    for key, val in kwargs.items():
        if val is not None:
            ssp_defaults[key] = val

    # Build the final command
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
        print(f"{BLUE}Output:\n{result.stdout}{RESET}")
    except subprocess.CalledProcessError as e:
        print(f"{RED}❌ Error running set_ssp_conf:{RESET}")
        print(f"{RED}stderr: {e.stderr}{RESET}")
        sys.exit(1)

class ScanMaskIntensity:
    """Iterates over both channel_mask and pulse_bias_percent_270nm."""
    def __init__(self, config):
        self.config = config
        self.mask_values = config.get("mask_values", [1])
        self.min_bias = config.get("min_bias", 4000)
        self.max_bias = config.get("max_bias", 4000)
        self.step = config.get("step", 500)

    def run(self):
        print(f"{YELLOW}📢 Starting SCAN MASK & INTENSITY TEST...{RESET}")
        for mask in self.mask_values:
            for bias in range(self.min_bias, self.max_bias + self.step, self.step):
                run_set_ssp_conf(
                    self.config,
                    channel_mask=mask,
                    pulse_bias_percent_270nm=bias
                )
                run_drunc_command(self.config)
                
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run configuration script using JSON input.")
    parser.add_argument("--config", required=True, help="Path to the configuration JSON file.")
    args = parser.parse_args()

    with open(args.config, "r") as file:
        config = json.load(file)

    # DTS setup
    dtsbutler = DTSButler(config)
    dtsbutler.run()

    # Web Proxy
    WebProxy.setup(config)

    # Daphne config
    run_daphne_config(config)

    # Scan test
    scan_test = ScanMaskIntensity(config)
    scan_test.run()

# if __name__ == "__main__":
#     # Set up argument parser
#     parser = argparse.ArgumentParser(description="Run configuration script using JSON input.")
#     parser.add_argument("--config", required=True, help="Path to the configuration JSON file.")
    
#     args = parser.parse_args()

#     # Load configuration from JSON file
#     with open(args.config, "r") as file:
#         config = json.load(file)

#     # Setup and run DTSButler
#     dtsbutler = DTSButler(config)
#     dtsbutler.run()

#     # Setup Web Proxy
#     WebProxy.setup(config)

#     # Execute the Daphne configuration
#     run_daphne_config(config)

#     # Execute the Scan Test
#     scan_test = ScanMaskIntensity(config)
#     scan_test.run()