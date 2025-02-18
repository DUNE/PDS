#!/usr/bin/env python3

import sys
import subprocess
import json
import argparse

def run_daphne_config(config_file):
    """Executes set_daphne_conf.py using parameters from a JSON config file."""

    # Load configuration from JSON
    try:
        with open(config_file, "r") as file:
            config = json.load(file)
    except FileNotFoundError:
        print(f"Error: Configuration file '{config_file}' not found.")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON format in '{config_file}'.")
        sys.exit(1)

    # Construct the command to execute set_daphne_conf.py
    cmd = [
        sys.executable,  # Use the current Python interpreter
        "set_daphne_conf.py",  # Path to the script
        config["daphne_details"],
        config["daphne_xml"],
        config["daphne_obj"]
    ]

    # Add optional arguments if provided
    if "attenuators" in config:
        cmd.extend(["--attenuators", config["attenuators"]])
    if "daphne_channels" in config:
        cmd.extend(["--daphne_channels", config["daphne_channels"]])
    if "bias" in config:
        cmd.extend(["--bias", config["bias"]])
    if "trim" in config:
        cmd.extend(["--trim", str(config["trim"])])

    # Print and execute the command
    print(f"\n=== Running set_daphne_conf.py with arguments: {' '.join(cmd)} ===")
    result = subprocess.call(cmd)

    # Check execution result
    if result != 0:
        print("\nError: set_daphne_conf.py command failed.")
        sys.exit(1)

if __name__ == "__main__":
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Run set_daphne_conf.py using a JSON configuration file.")
    parser.add_argument("--config", required=True, help="Path to the JSON configuration file.")
    
    args = parser.parse_args()

    # Run Daphne configuration
    run_daphne_config(args.config)