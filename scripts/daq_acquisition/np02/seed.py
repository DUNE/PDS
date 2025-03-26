#!/usr/bin/env python3

import json
import click
import copy

CONFIGURATIONS = [
    "daphne_full_mode",
    "full_mode_bias_off",
    "np02-daphne-running",
    "selftrigger_bias_off"
]

def get_channel_ids(device):
    if "range" in device["channels"]:
        return list(range(device["channels"]["range"][0], device["channels"]["range"][1] + 1))
    return device["channels"].get("indices", [])

def get_channel_analog_conf(channel_ids, common_conf, device):
    gains = [common_conf["offset_gain"]] * len(channel_ids)
    offsets = device["channels"]["offsets"]
    trims = [
        device["channels"]["trim"][idx] if idx < len(device["channels"]["trim"]) else 0
        for idx in channel_ids
    ]
    return {"ids": channel_ids, "gains": gains, "offsets": offsets, "trims": trims}

def map_channels_to_afes(channel_ids, num_afes=5, channels_per_afe=8):
    afe_channels = {afe: [] for afe in range(num_afes)}
    for channel_id in channel_ids:
        afe_id = channel_id // channels_per_afe
        if afe_id in afe_channels:
            afe_channels[afe_id].append(channel_id)
    return afe_channels

def populate_afes(afe_channels, device, common_conf, configuration):
    for afe_id, channels in afe_channels.items():
        if channels:
            configuration["afes"]["ids"].append(afe_id)

            attenuators = device["channels"].get("attenuators", [])
            biases = device["channels"].get("bias", [])
            if afe_id >= len(attenuators) or afe_id >= len(biases):
                raise ValueError(f"AFE {afe_id} has missing attenuators or biases in device {device['ip']}")

            configuration["afes"]["attenuators"].append(attenuators[afe_id])
            configuration["afes"]["v_biases"].append(biases[afe_id])

            configuration["afes"]["adcs"]["resolution"].append(common_conf["resolution"])
            configuration["afes"]["adcs"]["output_format"].append(common_conf["output_format"])
            configuration["afes"]["adcs"]["SB_first"].append(common_conf["SB_first"])

            configuration["afes"]["pgas"]["lpf_cut_frequency"].append(common_conf["lpf_cut_frequency"])
            configuration["afes"]["pgas"]["integrator_disable"].append(common_conf["pga_integrator_disable"])
            configuration["afes"]["pgas"]["gain"].append(common_conf["pga_gain"])

            configuration["afes"]["lnas"]["clamp"].append(common_conf["clamp"])
            configuration["afes"]["lnas"]["integrator_disable"].append(common_conf["lna_integrator_disable"])
            configuration["afes"]["lnas"]["gain"].append(common_conf["lna_gain"])

def generate_configuration(data, config_name):
    data = copy.deepcopy(data)  # Don't modify original input
    data["metadata"]["configuration"] = config_name
    configurations = {}

    common_conf = data["common_conf"]

    for device in data["devices"]:
        device = copy.deepcopy(device)  # avoid cross-contamination between config variants
        channel_ids = get_channel_ids(device)
        full_stream_channels = channel_ids if device["mode"] == "full_streaming" else []

        threshold = device.get("self_trigger_threshold", 0)
        bias = device["channels"].get("bias", [])

        if config_name == "daphne_full_mode":
            threshold = 0
        elif config_name == "full_mode_bias_off":
            threshold = 0
            bias = [0, 0, 0, 0, 0]
        elif config_name == "np02-daphne-running":
            pass
        elif config_name == "selftrigger_bias_off":
            if threshold == 0:
                raise ValueError(f"Threshold must be non-zero in 'selftrigger_bias_off' for device {device['ip']}")
        else:
            raise ValueError(f"Unsupported configuration type: {config_name}")

        device["channels"]["bias"] = bias
        self_trigger_threshold = threshold

        for field in ["self_trigger_xcorr", "tp_conf", "compensator", "inverter"]:
            if field not in device:
                raise ValueError(f"Missing '{field}' in device {device['ip']}")

        channel_analog_conf = get_channel_analog_conf(channel_ids, common_conf, device)

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
            "self_trigger_xcorr": device["self_trigger_xcorr"],
            "tp_conf": device["tp_conf"],
            "compensator": device["compensator"],
            "inverter": device["inverter"]
        }

        afe_channels = map_channels_to_afes(channel_ids)
        populate_afes(afe_channels, device, common_conf, configuration)

        configurations[device["ip"]] = configuration

    return configurations

@click.command()
@click.option("--details", "-df", required=True, help="Path to the input JSON file")
def run_seed(details):
    try:
        with open(details, "r") as file:
            base_data = json.load(file)

        for config_name in CONFIGURATIONS:
            print(f"Generating {config_name}.json ...")
            result = generate_configuration(base_data, config_name)
            with open(f"{config_name}.json", "w") as out:
                json.dump(result, out, indent=4)
        print("✅ All configuration files generated.")

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