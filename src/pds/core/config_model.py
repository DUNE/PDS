from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional, Tuple

from pydantic import BaseModel, ConfigDict, model_validator, field_validator, Extra

_LOG = logging.getLogger(__name__)


def _inclusive_range_values(start: int, stop: int, step: int) -> list[int]:
    if step == 0:
        raise ValueError("scan step must be non-zero.")
    if step > 0:
        if start > stop:
            return []
        values = list(range(start, stop + 1, step))
        if values[-1] != stop:
            values.append(stop)
        return values
    if start < stop:
        return []
    values = list(range(start, stop - 1, step))
    if values[-1] != stop:
        values.append(stop)
    return values


class BaseScanConfig(BaseModel):
    """
    Typed view of the user configuration JSON.
    Unknown keys are preserved via `extra="allow"` so we don't break callers.
    """
    mode: str
    drunc_working_dir: Path
    db_folder: Optional[str] = None
    oks_segment_file: Optional[str] = None
    oks_file: Optional[str] = None
    oks_session: Optional[str] = None
    session_name: Optional[str] = None
    drunc_target: str = "main-np02-pds"
    daphne_details: str
    daphne_obj: Optional[str] = None

    dry_run: bool = False
    plan_only: bool = False
    skip_dts: bool = False
    skip_daphne_conf: bool = False
    skip_ssp_conf: bool = False

    # thresholds (new)
    min_self_trigger_threshold: Optional[int] = None
    max_self_trigger_threshold: Optional[int] = None
    self_trigger_threshold_step: Optional[int] = None

    # thresholds (deprecated)
    min_corr: Optional[int] = None
    max_corr: Optional[int] = None
    corr_step: Optional[int] = None

    # attenuator scan
    min_att: Optional[int] = None
    max_att: Optional[int] = None
    att_step: Optional[int] = None

    # offset scan
    min_offset: Optional[int] = None
    max_offset: Optional[int] = None
    offset_step: Optional[int] = None

    # trim scan
    min_trim: Optional[int] = None
    max_trim: Optional[int] = None
    trim_step: Optional[int] = None

    # LED intensity scan
    min_led_intensity: Optional[int] = None
    max_led_intensity: Optional[int] = None
    led_intensity_step: Optional[int] = None
    led_intensity_values: Optional[list[int]] = None

    # LED intensity scan (legacy names)
    min_bias: Optional[int] = None
    max_bias: Optional[int] = None
    bias_step: Optional[int] = None
    step: Optional[int] = None

    # AFE SiPM bias scan
    min_afe_bias: Optional[int] = None
    max_afe_bias: Optional[int] = None
    afe_bias_step: Optional[int] = None
    afe_bias_values: Optional[list[int]] = None
    afe_bias_ids: Optional[list[int]] = None
    fixed_afe_biases: Optional[dict[int, int]] = None

    # Optional selectors for board-keyed DAPHNE configs.
    board_ids: Optional[list[str]] = None
    afe_ids: Optional[list[int]] = None
    channel_ids: Optional[list[int]] = None
    bias_ctrl: Optional[int] = None

    # misc
    mask_values: Optional[list[int]] = None
    drunc_delay_s: int = 20

    model_config = ConfigDict(extra="allow")

    @model_validator(mode="before")
    @classmethod
    def _warn_deprecated(cls, values: dict[str, Any]) -> dict[str, Any]:
        for key in ("min_corr", "max_corr", "corr_step"):
            if key in values:
                _LOG.warning("Config key '%s' is deprecated; use self_trigger_threshold_* instead.", key)
        return values

    @field_validator("mode")
    @classmethod
    def _mode_not_empty(cls, v: str) -> str:
        if not v:
            raise ValueError("mode must be set")
        return v

    def resolved_oks_file(self) -> Optional[str]:
        if self.oks_file:
            return self.oks_file
        if self.db_folder and self.oks_segment_file:
            return f"{self.db_folder}/segments/{self.oks_segment_file}"
        return None

    def thresholds(self) -> Tuple[int, int, int]:
        """Return (min, max, step) for self-trigger thresholds with fallbacks."""
        min_thr = self.min_self_trigger_threshold
        max_thr = self.max_self_trigger_threshold
        step = self.self_trigger_threshold_step

        if min_thr is None:
            min_thr = self.__dict__.get("min_corr")
        if max_thr is None:
            max_thr = self.__dict__.get("max_corr")
        if step is None:
            step = self.__dict__.get("corr_step")

        # Basic defaults if still missing
        min_thr = 0 if min_thr is None else int(min_thr)
        max_thr = min_thr if max_thr is None else int(max_thr)
        step = 1 if step is None else int(step)

        if step == 0:
            raise ValueError("self_trigger_threshold_step/corr_step must be non-zero.")
        return min_thr, max_thr, step

    def att_range(self) -> Tuple[int, int, int]:
        min_att = 0 if self.min_att is None else int(self.min_att)
        max_att = min_att if self.max_att is None else int(self.max_att)
        step = 1 if self.att_step is None else int(self.att_step)
        if step == 0:
            raise ValueError("att_step must be non-zero.")
        return min_att, max_att, step

    def offset_range(self) -> Tuple[int, int, int]:
        min_off = 0 if self.min_offset is None else int(self.min_offset)
        max_off = min_off if self.max_offset is None else int(self.max_offset)
        step = 1 if self.offset_step is None else int(self.offset_step)
        if step == 0:
            raise ValueError("offset_step must be non-zero.")
        return min_off, max_off, step

    def trim_range(self) -> Tuple[int, int, int]:
        min_trim = 0 if self.min_trim is None else int(self.min_trim)
        max_trim = min_trim if self.max_trim is None else int(self.max_trim)
        step = 1 if self.trim_step is None else int(self.trim_step)
        if step == 0:
            raise ValueError("trim_step must be non-zero.")
        return min_trim, max_trim, step

    def led_intensities(self) -> list[int]:
        if self.led_intensity_values:
            return [int(v) for v in self.led_intensity_values]

        min_intensity = self.min_led_intensity
        max_intensity = self.max_led_intensity
        step = self.led_intensity_step

        if min_intensity is None:
            min_intensity = self.min_bias
        if max_intensity is None:
            max_intensity = self.max_bias
        if step is None:
            step = self.bias_step
        if step is None:
            step = self.step

        min_intensity = 0 if min_intensity is None else int(min_intensity)
        max_intensity = min_intensity if max_intensity is None else int(max_intensity)
        step = 1 if step is None else int(step)
        return _inclusive_range_values(min_intensity, max_intensity, step)

    def afe_biases(self) -> list[int]:
        if self.afe_bias_values:
            return [int(v) for v in self.afe_bias_values]

        min_bias = 0 if self.min_afe_bias is None else int(self.min_afe_bias)
        max_bias = min_bias if self.max_afe_bias is None else int(self.max_afe_bias)
        step = 1 if self.afe_bias_step is None else int(self.afe_bias_step)
        return _inclusive_range_values(min_bias, max_bias, step)

    def masks(self) -> list[int]:
        if not self.mask_values:
            ssp_conf = getattr(self, "ssp_conf", None)
            if isinstance(ssp_conf, dict) and "channel_mask" in ssp_conf:
                return [int(ssp_conf["channel_mask"])]
            return [1]
        return [int(m) for m in self.mask_values]

    def dailycalib_entries(self) -> list[dict[str, Any]]:
        configured = getattr(self, "dailycalib", None)
        if configured:
            entries: list[dict[str, Any]] = []
            default_mask = self.masks()[0]
            for pulse in configured:
                entries.append(
                    {
                        "mask": int(pulse.get("mask", default_mask)),
                        "intensities": [int(v) for v in pulse.get("intensities", [0])],
                    }
                )
            return entries

        intensities = self.led_intensities()
        if not intensities:
            intensities = [0]
        return [{"mask": mask, "intensities": intensities} for mask in self.masks()]


class ThresholdScanConfig(BaseScanConfig):
    mode: str = "sthscan"


class AttScanConfig(BaseScanConfig):
    mode: str = "attscan"
    min_att: int
    max_att: int
    att_step: int


class OffsetScanConfig(BaseScanConfig):
    mode: str = "offsetscan"
    min_offset: int
    max_offset: int
    offset_step: int


class TrimScanConfig(BaseScanConfig):
    mode: str = "trimscan"
    min_trim: int
    max_trim: int
    trim_step: int


class LedIntensityScanConfig(BaseScanConfig):
    mode: str = "calibrun"


class AfeBiasScanConfig(BaseScanConfig):
    mode: str = "afebiasscan"


ScanConfig = BaseScanConfig
