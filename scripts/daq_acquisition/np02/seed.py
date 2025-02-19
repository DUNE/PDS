#!/usr/bin/env python3

import json
import click

# Function to determine channel IDs and full_stream_channels
def get_channel_ids(device):
    if "range" in device["channels"]:
        return list(range(device["channels"]["range"][0], device["channels"]["range"][1] + 1))
    return device["channels"].get("indices", [])

# Function to initialize analog configurations
def get_channel_analog_conf(channel_ids, common_conf, device):
    gains = [common_conf["offset_gain"]] * len(channel_ids)
    offsets = list(device["channels"]["offsets"])
    trims = [
        device["channels"]["trim"][idx] if idx < len(device["channels"]["trim"]) else 0
        for idx in channel_ids
    ]
    return {"ids": channel_ids, "gains": gains, "offsets": offsets, "trims": trims}

# Function to map channels to AFEs
def map_channels_to_afes(channel_ids, num_afes=5, channels_per_afe=8):
    afe_channels = {afe: [] for afe in range(num_afes)}
    for channel_id in channel_ids:
        afe_id = channel_id // channels_per_afe
        if afe_id in afe_channels:
            afe_channels[afe_id].append(channel_id)
    return afe_channels

# Function to populate AFE configurations
def populate_afes(afe_channels, device, common_conf, configuration):
    for afe_id, channels in afe_channels.items():
        if channels:  # Only process AFEs with active channels
            configuration["afes"]["ids"].append(afe_id)

            # Validate attenuators and biases
            attenuators = device["channels"].get("attenuators", [])
            biases = device["channels"].get("bias", [])
            if afe_id >= len(attenuators) or afe_id >= len(biases):
                raise ValueError(f"AFE {afe_id} has missing attenuators or biases in device {device['ip']}")

            configuration["afes"]["attenuators"].append(attenuators[afe_id])
            configuration["afes"]["v_biases"].append(biases[afe_id])

            # Populate ADC, PGA, and LNA vectors
            configuration["afes"]["adcs"]["resolution"].append(common_conf["resolution"])
            configuration["afes"]["adcs"]["output_format"].append(common_conf["output_format"])
            configuration["afes"]["adcs"]["SB_first"].append(common_conf["SB_first"])

            configuration["afes"]["pgas"]["lpf_cut_frequency"].append(common_conf["lpf_cut_frequency"])
            configuration["afes"]["pgas"]["integrator_disable"].append(common_conf["pga_integrator_disable"])
            configuration["afes"]["pgas"]["gain"].append(common_conf["pga_gain"])

            configuration["afes"]["lnas"]["clamp"].append(common_conf["clamp"])
            configuration["afes"]["lnas"]["integrator_disable"].append(common_conf["lna_integrator_disable"])
            configuration["afes"]["lnas"]["gain"].append(common_conf["lna_gain"])

# Main function to generate configuration dictionary
def generate_configuration(data):
    configurations = {}
    for device in data["devices"]:
        common_conf = data["common_conf"]

        # Determine channel IDs and full_stream_channels
        channel_ids = get_channel_ids(device)
        full_stream_channels = channel_ids if device["mode"] == "full_streaming" else []

        # Validate self_trigger_threshold based on mode
        if device["mode"] == "full_streaming":
            self_trigger_threshold = 0
        elif device["mode"] == "self-trigger":
            if not (10 <= device["self_trigger_threshold"] <= 9000):
                raise ValueError(
                    f"Invalid self_trigger_threshold={device['self_trigger_threshold']} "
                    f"for device {device['ip']}. It must be between 10 and 9000."
                )
            self_trigger_threshold = device["self_trigger_threshold"]
        else:
            raise ValueError(f"Invalid mode '{device['mode']}' for device {device['ip']}.")

        # Initialize channel_analog_conf
        channel_analog_conf = get_channel_analog_conf(channel_ids, common_conf, device)

        # Initialize configuration dictionary
        configuration = {
            "slot": device['slot'],
            "bias_ctrl": common_conf['bias_ctrl'],
            "self_trigger_threshold": self_trigger_threshold,
            "full_stream_channels": full_stream_channels,
            "channel_analog_conf": channel_analog_conf,
            "afes": {
                "ids": [],
                "attenuators": [],
                "v_biases": [],
                "adcs": {"resolution": [], "output_format": [], "SB_first": []},
                "pgas": {"lpf_cut_frequency": [], "integrator_disable": [], "gain": []},
                "lnas": {"clamp": [], "integrator_disable": [], "gain": []},
            },
        }

        # Map channels to AFEs and populate AFE configurations
        afe_channels = map_channels_to_afes(channel_ids)
        populate_afes(afe_channels, device, common_conf, configuration)

        # Add to configurations using IP address as key
        configurations[device["ip"]] = configuration

    return configurations

@click.command()
@click.option("--details", "-df", default="details.json", help="Path to the input JSON file")
@click.option("--output", "-o", default="output.json", help="Path to the output JSON file")
def run_seed(details, output):
    try:
        # Load the input JSON file
        with open(details, "r") as file:
            detail = json.load(file)

        # Generate configuration details
        details = generate_configuration(detail)

        # Write the output JSON file
        with open(output, "w") as outfile:
            json.dump(details, outfile, indent=4)

        print(f"Configuration saved to {output}")

    except FileNotFoundError:
        print(f"Error: File {details} not found.")
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON format in {details}.")
    except ValueError as ve:
        print(f"Configuration Error: {ve}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    run_seed()
