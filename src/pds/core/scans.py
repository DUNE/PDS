from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Callable

from .config_model import ScanConfig
from .daphne import apply_daphne_patch
from .drunc import run_drunc_command
from .ssp import run_set_ssp_conf

_LOG = logging.getLogger(__name__)


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


def _update_attenuators(data: dict, value: int) -> None:
    for dev in data.get("devices", []):
        afe = dev.setdefault("afe", {})
        afe["attenuators"] = value


def _update_offset(data: dict, value: int) -> None:
    for dev in data.get("devices", []):
        channels = dev.setdefault("channels", {})
        channels["offset"] = value


def _update_trim(data: dict, value: int) -> None:
    for dev in data.get("devices", []):
        channels = dev.setdefault("channels", {})
        channels["trim"] = value


class _ScanRunner:
    def __init__(self, cfg: ScanConfig, *, tmp_dir: Path) -> None:
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
        masks = self.cfg.masks()
        ledrange = self.cfg.__dict__.get("dailycalib", [{"mask": masks[0], "intensities": [0]}])

        _LOG.info("📢  Attenuator scan: %s → %s (step %s)", min_att, max_att, step)

        for att in att_range:
            self._apply_daphne(lambda data, a=att: _update_attenuators(data, a), "attenuators")
            for pulse in ledrange:
                mask = pulse.get("mask", masks[0])
                for bias in pulse.get("intensities", [0]):
                    _LOG.info("   ledrange bias=%s mask=%s att=%s", bias, mask, att)
                    self._run_ssp_and_drunc(
                        mask=mask,
                        bias=bias,
                        delay_s=self.cfg.drunc_delay_s,
                    )


class OffsetScan(_ScanRunner):
    def run(self) -> None:
        min_off, max_off, step = self.cfg.offset_range()
        off_range = range(min_off, max_off + step, step)
        masks = self.cfg.masks()
        ledrange = self.cfg.__dict__.get("dailycalib", [{"mask": masks[0], "intensities": [0]}])

        _LOG.info("📢  Offset scan: %s → %s (step %s)", min_off, max_off, step)

        for off in off_range:
            self._apply_daphne(lambda data, o=off: _update_offset(data, o), "offset")
            for pulse in ledrange:
                mask = pulse.get("mask", masks[0])
                for bias in pulse.get("intensities", [0]):
                    _LOG.info("   bias=%s mask=%s offset=%s", bias, mask, off)
                    self._run_ssp_and_drunc(
                        mask=mask,
                        bias=bias,
                        delay_s=self.cfg.drunc_delay_s,
                    )


class TrimScan(_ScanRunner):
    def run(self) -> None:
        min_trim, max_trim, step = self.cfg.trim_range()
        trim_range = range(min_trim, max_trim + step, step)
        masks = self.cfg.masks()
        ledrange = self.cfg.__dict__.get("dailycalib", [{"mask": masks[0], "intensities": [0]}])

        _LOG.info("📢  Trim scan: %s → %s (step %s)", min_trim, max_trim, step)

        for trim in trim_range:
            self._apply_daphne(lambda data, t=trim: _update_trim(data, t), "trim")
            for pulse in ledrange:
                mask = pulse.get("mask", masks[0])
                for bias in pulse.get("intensities", [0]):
                    _LOG.info("   bias=%s mask=%s trim=%s", bias, mask, trim)
                    self._run_ssp_and_drunc(
                        mask=mask,
                        bias=bias,
                        delay_s=self.cfg.drunc_delay_s,
                    )
