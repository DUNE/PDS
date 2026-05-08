from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Callable, Iterable

from .config_model import BaseScanConfig
from .daphne import apply_daphne_patch
from .drunc import run_drunc_command
from .ssp import run_set_ssp_conf

_LOG = logging.getLogger(__name__)


def _as_int_set(values: Iterable[int | str] | None) -> set[int] | None:
    if values is None:
        return None
    return {int(v) for v in values}


def _board_id_set(cfg: BaseScanConfig) -> set[str] | None:
    if cfg.board_ids is None:
        return None
    return {str(v) for v in cfg.board_ids}


def _iter_board_maps(data: dict, cfg: BaseScanConfig | None = None):
    selected_boards = _board_id_set(cfg) if cfg is not None else None
    for board_id, dev in data.items():
        if not isinstance(board_id, str) or not board_id.isdigit():
            continue
        if selected_boards is not None and board_id not in selected_boards:
            continue
        if isinstance(dev, dict):
            yield board_id, dev


def _section_ids(section: dict, field: str, target_ids: set[int] | None, default_count: int) -> list[int]:
    raw_ids = section.get("ids")
    if isinstance(raw_ids, list) and raw_ids:
        return [int(v) for v in raw_ids]

    values = section.get(field)
    if isinstance(values, list) and values:
        ids = list(range(len(values)))
    elif target_ids:
        ids = sorted(target_ids)
    else:
        ids = list(range(default_count))

    if ids:
        section["ids"] = ids
    return ids


def _section_vector(section: dict, field: str, ids: list[int], default: int = 0) -> list[int]:
    values = section.get(field)
    if isinstance(values, list):
        vector = [int(v) for v in values]
    elif values is None:
        vector = [default] * len(ids)
    else:
        vector = [int(values)] * len(ids)

    if len(vector) < len(ids):
        fill = vector[-1] if vector else default
        vector.extend([fill] * (len(ids) - len(vector)))
    elif len(vector) > len(ids):
        vector = vector[: len(ids)]

    section[field] = vector
    return vector


def _target_indices(ids: list[int], target_ids: set[int] | None) -> list[int]:
    if target_ids is None:
        return list(range(len(ids)))
    return [idx for idx, item in enumerate(ids) if int(item) in target_ids]


def _update_board_vector(
    dev: dict,
    section_name: str,
    field: str,
    value: int,
    *,
    target_ids: set[int] | None,
    default_count: int,
) -> None:
    section = dev.setdefault(section_name, {})
    ids = _section_ids(section, field, target_ids, default_count)
    values = _section_vector(section, field, ids)
    for idx in _target_indices(ids, target_ids):
        values[idx] = int(value)


def _update_self_trigger_threshold(data: dict, value: int) -> None:
    if isinstance(data, dict) and "devices" in data:
        for dev in data.get("devices", []):
            trigger = dev.setdefault("self_trigger", {})
            trigger["threshold"] = value
    else:
        # Handle board-id keyed maps (e.g., {"61": {...}})
        for _, dev in list(data.items()):
            if isinstance(dev, dict):
                if "self_trigger_threshold" in dev:
                    dev["self_trigger_threshold"] = value
                else:
                    trigger = dev.setdefault("self_trigger", {})
                    trigger["threshold"] = value


def _update_attenuators(data: dict, value: int, cfg: BaseScanConfig) -> None:
    if "devices" in data:
        for dev in data.get("devices", []):
            afe = dev.setdefault("afe", {})
            afe["attenuators"] = value
        return

    target_ids = _as_int_set(cfg.afe_ids)
    for _, dev in _iter_board_maps(data, cfg):
        _update_board_vector(
            dev,
            "afes",
            "attenuators",
            value,
            target_ids=target_ids,
            default_count=5,
        )


def _update_offset(data: dict, value: int, cfg: BaseScanConfig) -> None:
    if "devices" in data:
        for dev in data.get("devices", []):
            channels = dev.setdefault("channels", {})
            channels["offset"] = value
        return

    target_ids = _as_int_set(cfg.channel_ids)
    for _, dev in _iter_board_maps(data, cfg):
        _update_board_vector(
            dev,
            "channel_analog_conf",
            "offsets",
            value,
            target_ids=target_ids,
            default_count=0,
        )


def _update_trim(data: dict, value: int, cfg: BaseScanConfig) -> None:
    if "devices" in data:
        for dev in data.get("devices", []):
            channels = dev.setdefault("channels", {})
            channels["trim"] = value
        return

    target_ids = _as_int_set(cfg.channel_ids)
    for _, dev in _iter_board_maps(data, cfg):
        _update_board_vector(
            dev,
            "channel_analog_conf",
            "trims",
            value,
            target_ids=target_ids,
            default_count=0,
        )


def _update_afe_bias(data: dict, value: int, cfg: BaseScanConfig) -> None:
    if "devices" in data:
        for dev in data.get("devices", []):
            channels = dev.setdefault("channels", {})
            channels["bias"] = value
            if cfg.bias_ctrl is not None:
                dev["bias_ctrl"] = int(cfg.bias_ctrl)
        return

    scan_targets = _as_int_set(cfg.afe_bias_ids) or _as_int_set(cfg.afe_ids)
    fixed = {int(k): int(v) for k, v in (cfg.fixed_afe_biases or {}).items()}
    for _, dev in _iter_board_maps(data, cfg):
        if cfg.bias_ctrl is not None:
            dev["bias_ctrl"] = int(cfg.bias_ctrl)

        target_ids = scan_targets
        if target_ids is None and fixed:
            afes = dev.get("afes", {})
            ids = _section_ids(afes, "v_biases", None, 5)
            target_ids = {afe_id for afe_id in ids if afe_id not in fixed}

        _update_board_vector(
            dev,
            "afes",
            "v_biases",
            value,
            target_ids=target_ids,
            default_count=5,
        )

        if fixed:
            afes = dev.setdefault("afes", {})
            ids = _section_ids(afes, "v_biases", set(fixed), 5)
            values = _section_vector(afes, "v_biases", ids)
            for idx in _target_indices(ids, set(fixed)):
                values[idx] = fixed[ids[idx]]


class _ScanRunner:
    def __init__(self, cfg: BaseScanConfig, *, tmp_dir: Path) -> None:
        self.cfg = cfg
        self.tmp_dir = tmp_dir
        self.details_path = Path(cfg.drunc_working_dir) / cfg.daphne_details
        oks_file = cfg.resolved_oks_file()
        self.xml_path = Path(cfg.drunc_working_dir) / oks_file if oks_file else Path(cfg.drunc_working_dir)
        self._current_details: dict | None = None

    def _apply_daphne(self, mutate: Callable[[dict], None], description: str) -> None:
        if self.cfg.skip_daphne_conf:
            _LOG.info("  Skipping daphne configuration (skip_daphne_conf=True)...")
            return
        self._current_details = apply_daphne_patch(
            self.cfg,
            details_path=self.details_path,
            xml_path=self.xml_path,
            tmp_dir=self.tmp_dir,
            mutate=mutate,
            description=description,
            current_state=self._current_details,
        )

    def _run_ssp_and_drunc(self, *, mask: int, bias: int, delay_s: int) -> None:
        cfg_dict = self.cfg.model_dump(mode="python")
        oks_file = self.cfg.resolved_oks_file()
        if oks_file:
            cfg_dict["oks_file"] = oks_file
        else:
            _LOG.warning("No oks_file resolved; skipping SSP/drunc commands.")
            return
        if cfg_dict.get("plan_only"):
            _LOG.info("plan_only=True; would set SSP mask=%s bias=%s and run drunc.", mask, bias)
            run_drunc_command(cfg_dict, post_delay_s=delay_s)
            return
        run_set_ssp_conf(cfg_dict, channel_mask=mask, pulse_bias_percent_270nm=bias)
        run_drunc_command(cfg_dict, post_delay_s=delay_s)


class SelfTriggerScan(_ScanRunner):
    def run(self) -> None:
        min_thr, max_thr, step = self.cfg.thresholds()
        thr_range = range(min_thr, max_thr + step, step)

        _LOG.info("📢  Self-trigger threshold scan: %s → %s (step %s)", min_thr, max_thr, step)

        for thr in thr_range:
            _LOG.info("📢  self-trigger threshold = %s", thr)
            self._apply_daphne(lambda data, t=thr: _update_self_trigger_threshold(data, t), "self-trigger")
            self._run_ssp_and_drunc(
                mask=self.cfg.masks()[0],
                bias=0,
                delay_s=self.cfg.drunc_delay_s,
            )


class AttenuatorScan(_ScanRunner):
    def run(self) -> None:
        min_att, max_att, step = self.cfg.att_range()
        att_range = range(min_att, max_att + step, step)
        ledrange = self.cfg.dailycalib_entries()

        _LOG.info("📢  Attenuator scan: %s → %s (step %s)", min_att, max_att, step)

        for att in att_range:
            self._apply_daphne(lambda data, a=att: _update_attenuators(data, a, self.cfg), "attenuators")
            for pulse in ledrange:
                mask = pulse["mask"]
                for intensity in pulse["intensities"]:
                    _LOG.info("   led intensity=%s mask=%s att=%s", intensity, mask, att)
                    self._run_ssp_and_drunc(
                        mask=mask,
                        bias=intensity,
                        delay_s=self.cfg.drunc_delay_s,
                    )


class OffsetScan(_ScanRunner):
    def run(self) -> None:
        min_off, max_off, step = self.cfg.offset_range()
        off_range = range(min_off, max_off + step, step)
        ledrange = self.cfg.dailycalib_entries()

        _LOG.info("📢  Offset scan: %s → %s (step %s)", min_off, max_off, step)

        for off in off_range:
            self._apply_daphne(lambda data, o=off: _update_offset(data, o, self.cfg), "offset")
            for pulse in ledrange:
                mask = pulse["mask"]
                for intensity in pulse["intensities"]:
                    _LOG.info("   led intensity=%s mask=%s offset=%s", intensity, mask, off)
                    self._run_ssp_and_drunc(
                        mask=mask,
                        bias=intensity,
                        delay_s=self.cfg.drunc_delay_s,
                    )


class TrimScan(_ScanRunner):
    def run(self) -> None:
        min_trim, max_trim, step = self.cfg.trim_range()
        trim_range = range(min_trim, max_trim + step, step)
        ledrange = self.cfg.dailycalib_entries()

        _LOG.info("📢  Trim scan: %s → %s (step %s)", min_trim, max_trim, step)

        for trim in trim_range:
            self._apply_daphne(lambda data, t=trim: _update_trim(data, t, self.cfg), "trim")
            for pulse in ledrange:
                mask = pulse["mask"]
                for intensity in pulse["intensities"]:
                    _LOG.info("   led intensity=%s mask=%s trim=%s", intensity, mask, trim)
                    self._run_ssp_and_drunc(
                        mask=mask,
                        bias=intensity,
                        delay_s=self.cfg.drunc_delay_s,
                    )


class LedIntensityScan(_ScanRunner):
    def run(self) -> None:
        ledrange = self.cfg.dailycalib_entries()

        _LOG.info("📢  LED intensity scan across %s mask configuration(s)", len(ledrange))

        for pulse in ledrange:
            mask = pulse["mask"]
            for intensity in pulse["intensities"]:
                _LOG.info("   led intensity=%s mask=%s", intensity, mask)
                self._run_ssp_and_drunc(
                    mask=mask,
                    bias=intensity,
                    delay_s=self.cfg.drunc_delay_s,
                )


class AfeBiasScan(_ScanRunner):
    def run(self) -> None:
        ledrange = self.cfg.dailycalib_entries()
        biases = self.cfg.afe_biases()

        _LOG.info("📢  AFE bias scan across %s bias value(s)", len(biases))

        for afe_bias in biases:
            self._apply_daphne(lambda data, b=afe_bias: _update_afe_bias(data, b, self.cfg), "AFE bias")
            for pulse in ledrange:
                mask = pulse["mask"]
                for intensity in pulse["intensities"]:
                    _LOG.info("   led intensity=%s mask=%s afe_bias=%s", intensity, mask, afe_bias)
                    self._run_ssp_and_drunc(
                        mask=mask,
                        bias=intensity,
                        delay_s=self.cfg.drunc_delay_s,
                    )
