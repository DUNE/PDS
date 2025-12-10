from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional, Tuple

from pydantic import BaseModel, ConfigDict, model_validator, field_validator

_LOG = logging.getLogger(__name__)


class ScanConfig(BaseModel):
    """
    Typed view of the user configuration JSON.
    Unknown keys are preserved via `extra="allow"` so we don't break callers.
    """

    mode: str
    drunc_working_dir: Path
    oks_file: str
    oks_session: Optional[str] = None
    session_name: Optional[str] = None
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

    def masks(self) -> list[int]:
        if not self.mask_values:
            return [1]
        return [int(m) for m in self.mask_values]
