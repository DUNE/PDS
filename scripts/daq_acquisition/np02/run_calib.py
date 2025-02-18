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
        web_proxy_cmd = config["web_proxy_cmd"]
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
        self.dts_align_cmd = config["dts_align_cmd"]
        self.dts_faketrig_cmd_template = config["dts_faketrig_cmd_template"]

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
        "/nfs/home/marroyav/fddaq-v5.2.1-a9/pds/scripts/daq_acquisition/np02/set_daphne_conf.py",
        config["daphne_details"],
        config["oks_file"],
        config["daphne_obj"]
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
        f"{config['oks_session']} {config['session_name']} "
        f"boot conf start enable-triggers change-rate {config['change_rate']} wait {config['wait_time']} "
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
    """Runs the set_ssp_conf script with the provided arguments."""
    oks_file = config["oks_file"]
    cmd = ["set_ssp_conf", oks_file]

    for key, value in kwargs.items():
        if value is not None:
            option = f"--{key.replace('_', '-')}"
            cmd.append(option)
            cmd.append(str(value))

    print(f"{YELLOW}📢 Running set_ssp_conf...{RESET}")
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
        """Nested loop over channel_mask and pulse_bias_percent_270nm."""
        print(f"{YELLOW}📢 Starting SCAN MASK & INTENSITY TEST...{RESET}")
        for mask in self.mask_values:
            for bias in range(self.min_bias, self.max_bias + self.step, self.step):
                run_set_ssp_conf(
                    self.config,
                    object_name="np02-ssp-on",
                    number_channels=12,
                    channel_mask=mask,
                    pulse_mode="single",
                    burst_count=1,
                    double_pulse_delay_ticks=0,
                    pulse1_width_ticks=5,
                    pulse2_width_ticks=0,
                    pulse_bias_percent_270nm=bias,
                    pulse_bias_percent_367nm=0
                )
                run_drunc_command(self.config)

if __name__ == "__main__":
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Run configuration script using JSON input.")
    parser.add_argument("--config", required=True, help="Path to the configuration JSON file.")
    
    args = parser.parse_args()

    # Load configuration from JSON file
    with open(args.config, "r") as file:
        config = json.load(file)

    # Setup Web Proxy
    WebProxy.setup(config)

    # Setup and run DTSButler
    dtsbutler = DTSButler(config)
    dtsbutler.run()

    # Execute the Daphne configuration
    run_daphne_config(config)

    # Execute the Scan Test
    scan_test = ScanMaskIntensity(config)
    scan_test.run()