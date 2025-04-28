from __future__ import annotations

"""
Generate the four NP02-DAPHNE configuration JSONs (“seeds”).

Changes vs. the original
------------------------
* Re-uses shared helpers in `constants.py` & `utils.py`
* Generates the four JSON files **in parallel** (ProcessPoolExecutor)
* Drops duplicated pretty-printer / bitmask code
* Adds type hints and small micro-optimisations
"""

import copy
import json
import logging
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict

from .constants import CHANNELS_PER_AFE, CONFIGURATIONS
from .utils import bitmask, pretty_compact_json


# -----------------------------------------------------------------------------#
# Helper functions (unchanged behaviour, tighter impl.)                        #
# -----------------------------------------------------------------------------#


def assemble_tp_conf(trigger: dict[str, Any]) -> int:
    filter_modes = {"compensated": 0, "inverted": 1, "xcorr": 2, "raw": 3}
    filter_mode = filter_modes.get(trigger.get("filter_mode", "inverted"), 1)
    slope_mode = 0 if str(trigger.get("slope_mode", "16")) == "16" else 1
    slope_threshold = trigger.get("slope_threshold", 12)
    pedestal_length = trigger.get("pedestal_length", 64)
    spybuffer_channel = trigger.get("spybuffer_channel", 63)

    pedestal_code = max(0, min(31, pedestal_length // 8))
    spy_code = max(0, min(63, spybuffer_channel))

    return (
        (filter_mode & 0x3)
        | ((slope_mode & 0x1) << 8)
        | ((slope_threshold & 0x7F) << 9)
        | ((pedestal_code & 0x1F) << 16)
        | ((spy_code & 0x3F) << 21)
    )


def get_channel_ids(device: dict[str, Any]) -> list[int]:
    if "range" in device["channels"]:
        start, end = device["channels"]["range"]
        return list(range(start, end + 1))
    return device["channels"].get("indices", [])


def get_channel_analog_conf(
    channel_ids: list[int],
    common_conf: dict[str, Any],
    device: dict[str, Any],
) -> dict[str, Any]:
    gains = [common_conf["offset_gain"]] * len(channel_ids)
    offsets = device["channels"].get("offsets", [])
    trims = [
        device["channels"].get("trim", [0] * len(channel_ids))[idx]
        if idx < len(device["channels"].get("trim", []))
        else 0
        for idx in channel_ids
    ]
    return {
        "ids": channel_ids,
        "gains": gains,
        "offsets": offsets,
        "trims": trims,
    }


def map_channels_to_afes(
    channel_ids: list[int], *, num_afes: int = 5
) -> dict[int, list[int]]:
    afe_channels: dict[int, list[int]] = {afe: [] for afe in range(num_afes)}
    for ch in channel_ids:
        afe_channels[ch // CHANNELS_PER_AFE].append(ch)
    return afe_channels


def populate_afes(
    afe_channels: dict[int, list[int]],
    device: dict[str, Any],
    common_conf: dict[str, Any],
    configuration: dict[str, Any],
) -> None:
    for afe_id, channels in afe_channels.items():
        if not channels:
            continue

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
        configuration["afes"]["adcs"]["output_format"].append(
            common_conf["output_format"]
        )
        configuration["afes"]["adcs"]["SB_first"].append(common_conf["SB_first"])

        configuration["afes"]["pgas"]["lpf_cut_frequency"].append(
            common_conf["lpf_cut_frequency"]
        )
        configuration["afes"]["pgas"]["integrator_disable"].append(
            common_conf["pga_integrator_disable"]
        )
        configuration["afes"]["pgas"]["gain"].append(common_conf["pga_gain"])

        configuration["afes"]["lnas"]["clamp"].append(common_conf["clamp"])
        configuration["afes"]["lnas"]["integrator_disable"].append(
            common_conf["lna_integrator_disable"]
        )
        configuration["afes"]["lnas"]["gain"].append(common_conf["lna_gain"])


# -----------------------------------------------------------------------------#
# Core generation                                                              #
# -----------------------------------------------------------------------------#


def generate_configuration(
    data: dict[str, Any], config_name: str
) -> dict[str, Any]:
    """Generate one of the four official NP02 configuration blobs."""
    data = copy.deepcopy(data)
    data["metadata"]["configuration"] = config_name

    configurations: Dict[str, Any] = {}
    common_conf = data["common_conf"]

    for device in data["devices"]:
        logging.info("Generating %s for device %s", config_name, device["ip"])
        device = copy.deepcopy(device)

        channel_ids = get_channel_ids(device)
        full_stream_channels = (
            channel_ids if config_name.startswith("np02_daphne_full_mode") else []
        )

        trigger = device.get("self_trigger", {})
        threshold = trigger.get("threshold", 0)
        bias = device["channels"].get("bias", [])

        if config_name == "np02_daphne_full_mode":
            threshold = 0
        elif config_name == "np02_daphne_full_mode_bias_off":
            threshold = 0
            bias = [0] * 5
        elif config_name == "np02_daphne_selftrigger":
            pass  # keep JSON values
        elif config_name == "np02_daphne_selftrigger_bias_off":
            bias = [0] * 5
            if threshold == 0:
                raise ValueError(
                    f"Threshold must be non-zero in 'selftrigger_bias_off' "
                    f"for device {device['ip']}"
                )
        else:
            raise ValueError(f"Unsupported configuration: {config_name}")

        device["channels"]["bias"] = bias

        xcorr_conf = trigger.get("self_trigger_xcorr", {})
        corr = xcorr_conf.get("correlation_threshold", 0)
        disc = xcorr_conf.get("discrimination_threshold", 0)
        self_trigger_xcorr = ((disc & 0x3FFF) << 28) | (corr & 0x0FFFFFFF)

        tp_conf = assemble_tp_conf(trigger)

        comp_list = trigger.get("enable_compensator", [])
        inv_list = trigger.get("enable_inverter", [])
        compensator = bitmask(comp_list)
        inverter = bitmask(inv_list)

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
                "pgas": {
                    "lpf_cut_frequency": [],
                    "integrator_disable": [],
                    "gain": [],
                },
                "lnas": {"clamp": [], "integrator_disable": [], "gain": []},
            },
            "self_trigger_xcorr": self_trigger_xcorr,
            "tp_conf": tp_conf,
            "compensator": compensator,
            "inverter": inverter,
        }

        afe_channels = map_channels_to_afes(channel_ids)
        populate_afes(afe_channels, device, common_conf, configuration)
        configurations[device["ip"]] = configuration

    return configurations


# -----------------------------------------------------------------------------#
# Public API                                                                   #
# -----------------------------------------------------------------------------#


def _worker(base_data: dict[str, Any], cfg: str, out_dir: Path) -> None:
    """Sub-process entry point (pickle-able)."""
    result = generate_configuration(base_data, cfg)
    (out_dir / f"{cfg}.json").write_text(pretty_compact_json(result))
    logging.info("Wrote %s.json", cfg)


def generate_seeds(details_path: str | Path) -> None:
    """
    Generate all four configuration files
    (`np02_daphne_*`) **in parallel** for speed.
    """
    try:
        logging.info("Reading input JSON: %s", details_path)
        with open(details_path, "r", encoding="utf-8") as fh:
            base_data = json.load(fh)

        out_dir = Path(details_path).parent

        with ProcessPoolExecutor() as ex:
            futs = {
                ex.submit(_worker, base_data, cfg, out_dir): cfg
                for cfg in CONFIGURATIONS
            }
            for fut in as_completed(futs):
                fut.result()  # propagate any exceptions

        logging.info("✅ All configuration files generated (parallel).")

    except FileNotFoundError:
        logging.error("Error: File %s not found.", details_path)
    except json.JSONDecodeError:
        logging.error("Error: Invalid JSON format in %s.", details_path)
    except ValueError as err:
        logging.error("Configuration error: %s", err)
    except Exception as exc:  # noqa: BLE001
        logging.exception("Unexpected error generating seeds: %s", exc)
