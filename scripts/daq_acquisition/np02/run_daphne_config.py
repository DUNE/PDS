#!/usr/bin/env python3

import subprocess
import sys
import argparse
import json

# ANSI escape codes for colors
YELLOW = "\033[93m"  # Warnings / Start messages
GREEN = "\033[92m"  # Success
RED = "\033[91m"  # Errors
RESET = "\033[0m"  # Reset color

def run_daphne_config(config):
    """Executes set_daphne_conf.py using parameters from the config dictionary."""
    cmd = [
        sys.executable,
        "/nfs/home/marroyav/fddaq-v5.2.1-a9/pds/scripts/daq_acquisition/np02/set_daphne_conf_new.py",
        config["daphne_details"],
        config["oks_file"],
        config["daphne_obj"],
        "--bias",
        f"{config['bias']}"
    ]

    print(f"{YELLOW}📢 Running set_daphne_conf.py...{RESET}")
    print(cmd)
    result = subprocess.call(cmd)

    if result != 0:
        print(f"{RED}❌ Error: set_daphne_conf.py command failed.{RESET}")
        sys.exit(1)
    print(f"{GREEN}✅ Daphne configuration completed.{RESET}")

if __name__ == "__main__":
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Run Daphne configuration script using JSON input.")
    parser.add_argument("--config", required=True, help="Path to the configuration JSON file.")
    
    args = parser.parse_args()

    # Load configuration from JSON file
    with open(args.config, "r") as file:
        config = json.load(file)

    # Execute the Daphne configuration
    run_daphne_config(config)
