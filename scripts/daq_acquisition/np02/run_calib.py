#!/usr/bin/env python3

import subprocess
import sys
import argparse
import json

class WebProxy:
    """Handles sourcing the web proxy at the beginning of execution."""
    
    @staticmethod
    def setup(config):
        """Sources the web proxy script from JSON configuration."""
        web_proxy_cmd = config["web_proxy_cmd"]
        print("\n=== Sourcing web_proxy.sh ===")
        result = subprocess.call(f"bash -c '{web_proxy_cmd}'", shell=True)
        if result != 0:
            print("\nError: Failed to source web_proxy.sh")
            sys.exit(1)

class DTSButler:
    """Handles the execution of DTS commands."""
    
    def __init__(self, config):
        self.hztrigger = config["hztrigger"]
        self.dts_align_cmd = config["dts_align_cmd"]
        self.dts_faketrig_cmd_template = config["dts_faketrig_cmd_template"]

    def run(self):
        """Runs DTS alignment and fake trigger configuration."""
        print("\n=== Running DTS Alignment Command ===")
        result = subprocess.call(self.dts_align_cmd, shell=True)
        if result != 0:
            print("\nError: DTS alignment command failed.")
            sys.exit(1)

        dts_faketrig_cmd = self.dts_faketrig_cmd_template.format(hztrigger=self.hztrigger)
        print(f"\n=== Running DTS Fake Trigger Command: {dts_faketrig_cmd} ===")
        result = subprocess.call(dts_faketrig_cmd, shell=True)
        if result != 0:
            print("\nError: DTS fake trigger command failed.")
            sys.exit(1)

def run_daphne_config(config):
    """Executes set_daphne_conf.py using parameters from the config dictionary."""
    cmd = [
        sys.executable,
        "set_daphne_conf.py",
        config["daphne_details"],
        config["oks_file"],
        config["daphne_obj"]
    ]

    print(f"\n=== Running set_daphne_conf.py with arguments: {' '.join(cmd)} ===")
    result = subprocess.call(cmd)

    if result != 0:
        print("\nError: set_daphne_conf.py command failed.")
        sys.exit(1)

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
    drunc_working_dir = config["drunc_working_dir"]  # Get working directory from config

    print(f"\n=== Running drunc-unified-shell from {drunc_working_dir} ===")
    print(f'{drunc_cmd}')
    result = subprocess.call(drunc_cmd, shell=True, cwd=drunc_working_dir)

    if result != 0:
        print("\nError: drunc-unified-shell command failed.")
        sys.exit(1)

def run_set_ssp_conf(config, **kwargs):
    """Runs the set_ssp_conf script with the provided arguments."""
    oks_file = config["oks_file"]

    cmd = ["set_ssp_conf", oks_file]

    for key, value in kwargs.items():
        if value is not None:
            option = f"--{key.replace('_', '-')}"
            cmd.append(option)
            cmd.append(str(value))

    try:
        result = subprocess.run(cmd, check=True, text=True, capture_output=True)
        print(f"\n=== Running set_ssp_conf with {kwargs} ===")
        print("Output:\n", result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"\nError running set_ssp_conf with {kwargs}:")
        print("stderr:", e.stderr)
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
    print("\n=== Running SCAN MASK & INTENSITY TEST ===")
    scan_test = ScanMaskIntensity(config)
    scan_test.run()