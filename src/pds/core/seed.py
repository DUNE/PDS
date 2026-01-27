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

from .constants import CHANNELS_PER_AFE, CONFIGURATIONS, ALWAYS_SELF_TRIGGER_IPS, NEVER_BIAS_IPS
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
    trims = device["channels"].get("trim", [])
    if not trims:
        trims = [0]*len(channel_ids)
    if len(trims) != len(channel_ids) or len(offsets) != len(channel_ids): 
        raise ValueError(f"The length of trim should be equal to channel_ids")
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
    attenuators = device["channels"].get("attenuators", [])
    biases = device["channels"].get("bias", [])

    for afe_id, channels in afe_channels.items():
        if not channels:
            continue

        configuration["afes"]["ids"].append(afe_id)

        try:
            configuration["afes"]["attenuators"].append(attenuators[afe_id])
            configuration["afes"]["v_biases"].append(biases[afe_id])
        except IndexError:
            raise ValueError(
                f"AFE {afe_id} requires attenuator/bias, but device {device['ip']} provides only "
                f"{len(attenuators)} attenuators and {len(biases)} biases"
            )

        configuration["afes"]["adcs"]["resolution"].append(common_conf["resolution"])
        configuration["afes"]["adcs"]["output_format"].append(common_conf["output_format"])
        configuration["afes"]["adcs"]["SB_first"].append(common_conf["SB_first"])

        configuration["afes"]["pgas"]["lpf_cut_frequency"].append(common_conf["lpf_cut_frequency"])
        configuration["afes"]["pgas"]["integrator_disable"].append(common_conf["pga_integrator_disable"])
        configuration["afes"]["pgas"]["gain"].append(common_conf["pga_gain"])

        configuration["afes"]["lnas"]["clamp"].append(common_conf["clamp"])
        configuration["afes"]["lnas"]["integrator_disable"].append(common_conf["lna_integrator_disable"])
        configuration["afes"]["lnas"]["gain"].append(common_conf["lna_gain"])

# -----------------------------------------------------------------------------#
# Core generation                                                              #
# -----------------------------------------------------------------------------#

def generate_configuration(
    data: dict[str, Any], config_name: str
) -> dict[str, Any]:
    """Generate one of the NP02-DAPHNE configuration blobs."""
    data = copy.deepcopy(data)
    data["metadata"]["configuration"] = config_name

    configurations: Dict[str, Any] = {}
    common_conf = data["common_conf"]

    for device in data["devices"]:
        logging.info("Generating %s for device %s", config_name, device.get("board_id", device.get("ip","?")))
        device = copy.deepcopy(device)

        # --- New required key & controller IP (backward compatible) ---
        board_id = str(device["board_id"])  # required in the new schema
        controller_ip = device.get("ip")

        channel_ids = get_channel_ids(device)

        # Allow matching either by IP or by board_id for your policy lists
        id_keys = {controller_ip, board_id}

        # Enforce fixed bias for NEVER_BIAS_IPS
        if any(k in NEVER_BIAS_IPS for k in id_keys):
            bias = [0] * 5
        else:
            bias = device["channels"].get("bias", [])

        trigger = device.get("self_trigger", {})
        if any(k in ALWAYS_SELF_TRIGGER_IPS for k in id_keys):
            threshold = 8000
        elif config_name == "np02_daphne_selftrigger":
            threshold = trigger.get("threshold", 0)
        elif config_name == "np02_daphne_fullstream":
            threshold = 0
            device["full_stream_channels"] = channel_ids
        else:
            raise ValueError(f"Unsupported configuration: {config_name}")

        # Apply fixed bias
        device["channels"]["bias"] = bias

        # Compute register values
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
            "detector_id": device["det_id"],
            "crate_id": device["crate_id"],
            "slot_id": device["slot_id"],  
            "ip": controller_ip,

            "bias_ctrl": common_conf["bias_ctrl"],
            "self_trigger_threshold": threshold,
            "full_stream_channels": device.get("full_stream_channels", []),
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

        # --- Key by board_id instead of IP ---
        configurations[board_id] = configuration

    return configurations



# -----------------------------------------------------------------------------#
# Public API                                                                   #
# -----------------------------------------------------------------------------#


def _worker(base_data: dict[str, Any], cfg: str, out_dir: Path) -> None:
    """Sub-process entry point (pickle-able)."""
    result = generate_configuration(base_data, cfg)
    (out_dir / f"{cfg}.json").write_text(pretty_compact_json(result, multiline=True))
    logging.info("Wrote %s.json", cfg)


def generate_seeds(details_path: str | Path, out_dir: str) -> None:
    """
    Generate all four configuration files
    (`np02_daphne_*`) **in parallel** for speed.
    """
    try:
        logging.info("Reading input JSON: %s", details_path)
        with open(details_path, "r", encoding="utf-8") as fh:
            base_data = json.load(fh)

        # No out_dir was given
        if not out_dir:
            out_dir = Path(details_path).parent
        else:
            out_dir = Path(out_dir)
            if not out_dir.is_dir():
                raise Exception(f"The path {out_dir.as_posix()} is not a directory")

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
