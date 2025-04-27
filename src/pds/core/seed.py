import logging
import json
import os
import copy
from pathlib import Path

CONFIGURATIONS = [
    "np02_daphne_full_mode",
    "np02_daphne_full_mode_bias_off",
    "np02_daphne_selftrigger",
    "np02_daphne_selftrigger_bias_off"
]

def pretty_compact_json(obj, indent=2):
    def _dump(obj, level):
        spacing = ' ' * (level * indent)
        if isinstance(obj, dict):
            items = []
            for k, v in obj.items():
                dumped = _dump(v, level + 1)
                items.append(f'{spacing}  "{k}": {dumped}')
            return '{\n' + ',\n'.join(items) + f'\n{spacing}}}'
        elif isinstance(obj, list):
            items = [_dump(v, level + 1) for v in obj]
            return '[\n' + ',\n'.join(f'{" " * ((level + 1) * indent)}{item}' for item in items) + f'\n{spacing}]'
        else:
            return json.dumps(obj)
    return _dump(obj, 0)

def bitmask_from_channels(channels):
    mask = 0
    for ch in channels:
        if 0 <= ch < 40:
            mask |= 1 << ch
    return mask

def assemble_tp_conf(trigger):
    filter_modes = {"compensated": 0, "inverted": 1, "xcorr": 2, "raw": 3}
    filter_mode = filter_modes.get(trigger.get("filter_mode", "inverted"), 1)
    slope_mode = 0 if str(trigger.get("slope_mode", "16")) == "16" else 1
    slope_threshold = trigger.get("slope_threshold", 12)
    pedestal_length = trigger.get("pedestal_length", 64)
    spybuffer_channel = trigger.get("spybuffer_channel", 63)

    pedestal_code = max(0, min(31, pedestal_length // 8))
    spy_code = max(0, min(63, spybuffer_channel))

    tp_conf = (
        (filter_mode & 0x3)
        | ((slope_mode & 0x1) << 8)
        | ((slope_threshold & 0x7F) << 9)
        | ((pedestal_code & 0x1F) << 16)
        | ((spy_code & 0x3F) << 21)
    )
    return tp_conf

def get_channel_ids(device):
    if "range" in device["channels"]:
        start, end = device["channels"]["range"]
        return list(range(start, end + 1))
    return device["channels"].get("indices", [])

def get_channel_analog_conf(channel_ids, common_conf, device):
    gains = [common_conf["offset_gain"]] * len(channel_ids)
    offsets = device["channels"].get("offsets", [])
    trims = [
        device["channels"].get("trim", [0]*len(channel_ids))[idx]
        if idx < len(device["channels"].get("trim", [])) else 0
        for idx in channel_ids
    ]
    return {
        "ids": channel_ids,
        "gains": gains,
        "offsets": offsets,
        "trims": trims
    }

def map_channels_to_afes(channel_ids, num_afes=5, channels_per_afe=8):
    afe_channels = {afe: [] for afe in range(num_afes)}
    for ch in channel_ids:
        afe_id = ch // channels_per_afe
        if afe_id in afe_channels:
            afe_channels[afe_id].append(ch)
    return afe_channels

def populate_afes(afe_channels, device, common_conf, configuration):
    for afe_id, channels in afe_channels.items():
        if channels:
            configuration["afes"]["ids"].append(afe_id)
            attenuators = device["channels"].get("attenuators", [])
            biases = device["channels"].get("bias", [])
            if afe_id >= len(attenuators) or afe_id >= len(biases):
                raise ValueError(
                    f"AFE {afe_id} has missing attenuators/biases in device {device['ip']}"
                )

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
    data = copy.deepcopy(data)
    data["metadata"]["configuration"] = config_name

    configurations = {}
    common_conf = data["common_conf"]

    for device in data["devices"]:
        logging.info(f"Generating config='{config_name}' for device='{device['ip']}'")
        device = copy.deepcopy(device)
        channel_ids = get_channel_ids(device)
        full_stream_channels = channel_ids if config_name.startswith("np02_daphne_full_mode") else []

        trigger = device.get("self_trigger", {})
        threshold = trigger.get("threshold", 0)
        bias = device["channels"].get("bias", [])

        if config_name == "np02_daphne_full_mode":
            threshold = 0
            logging.info("Overriding threshold=0 for np02_daphne_full_mode")
        elif config_name == "np02_daphne_full_mode_bias_off":
            threshold = 0
            bias = [0] * 5
            logging.info("Overriding threshold=0 and bias=0 for np02_daphne_full_mode_bias_off")
        elif config_name == "np02_daphne_selftrigger":
            logging.info("np02_daphne_selftrigger, using threshold and bias from JSON")
        elif config_name == "np02_daphne_selftrigger_bias_off":
            bias = [0] * 5
            if threshold == 0:
                raise ValueError(f"Threshold must be non-zero in 'selftrigger_bias_off' for device {device['ip']}")
            logging.info(f"np02_daphne_selftrigger_bias_off => forcing bias=0, threshold={threshold}")
        else:
            raise ValueError(f"Unsupported configuration type: {config_name}")

        device["channels"]["bias"] = bias

        xcorr_conf = trigger.get("self_trigger_xcorr", {})
        corr = xcorr_conf.get("correlation_threshold", 0)
        disc = xcorr_conf.get("discrimination_threshold", 0)
        self_trigger_xcorr = ((disc & 0x3FFF) << 28) | (corr & 0x0FFFFFFF)

        tp_conf = assemble_tp_conf(trigger)

        comp_list = trigger.get("enable_compensator", [])
        inv_list = trigger.get("enable_inverter", [])
        compensator = bitmask_from_channels(comp_list)
        inverter = bitmask_from_channels(inv_list)

        channel_analog_conf = get_channel_analog_conf(channel_ids, common_conf, device)
        configuration = {
            "slot": device["slot_id"],
            "bias_ctrl": common_conf["bias_ctrl"],
            "self_trigger_threshold": threshold,
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
            "self_trigger_xcorr": self_trigger_xcorr,
            "tp_conf": tp_conf,
            "compensator": compensator,
            "inverter": inverter
        }

        afe_channels = map_channels_to_afes(channel_ids)
        populate_afes(afe_channels, device, common_conf, configuration)
        configurations[device["ip"]] = configuration

    return configurations

def generate_seeds(details_path):
    try:
        logging.info(f"Reading input JSON: {details_path}")
        with open(details_path, "r") as file:
            base_data = json.load(file)

        output_dir = Path(details_path).parent

        for config_name in CONFIGURATIONS:
            logging.info(f"Generating {config_name}.json ...")
            result = generate_configuration(base_data, config_name)
            daphne_json = pretty_compact_json(result)

            output_file = output_dir / f"{config_name}.json"
            with open(output_file, "w") as f:
                f.write(daphne_json)

            logging.info(f"Wrote {output_file}")

        logging.info("✅ All configuration files generated.")

    except FileNotFoundError:
        logging.error(f"Error: File {details_path} not found.")
    except json.JSONDecodeError:
        logging.error(f"Error: Invalid JSON format in {details_path}.")
    except ValueError as ve:
        logging.error(f"Configuration Error: {ve}")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
