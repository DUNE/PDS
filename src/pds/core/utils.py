"""
Lightweight helper functions that several modules share.
(Deliberately kept free of heavy imports.)
"""

from __future__ import annotations

import json
from typing import Any

from .constants import JSON_INDENT

def pretty_compact_json(
    obj: Any,
    *,
    multiline: bool = False,
    indent: int = 2,
) -> str:
    """
    Convert *obj* to JSON.

    Parameters
    ----------
    obj        : any serialisable Python object
    multiline  : True  → formatted with new-lines & indentation
                 False → single line, minimal whitespace
    indent     : number of spaces per indent level when multiline=True
    """
    if not multiline:
        # single-line: remove the blank after ',' and ':'
        return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)

    # ---------- pretty version (what you had before) ----------
    def _dump(o: Any, level: int) -> str:
        spacing = " " * (level * indent)
        if isinstance(o, dict):
            parts = [
                f'{spacing}{" " * indent}"{k}": {_dump(v, level + 1)}'
                for k, v in o.items()
            ]
            return "{\n" + ",\n".join(parts) + f"\n{spacing}}}"
        if isinstance(o, list):
            parts = [_dump(v, level + 1) for v in o]
            return (
                "[\n"
                + ",\n".join(
                    f'{" " * ((level + 1) * indent)}{p}' for p in parts
                )
                + f"\n{spacing}]"
            )
        return json.dumps(o, ensure_ascii=False)

    return _dump(obj, 0)


def bitmask(channels: list[int], *, width: int = 40) -> int:
    """Convert a list of channel indices to a bitmask (ignoring out-of-range)."""
    return sum(1 << ch for ch in channels if 0 <= ch < width)

    
def setup_led_range(mode, min_bias, max_bias, step):
    """
    min_bias can be a vector when performing a calibration, this allow for
    a scan with values set by the user, otherwise, it will scan over
    between min_bias, max_bias given the step
    """
    if isinstance(min_bias,list):
        if mode not in ["calibration", "attscan"]:
            raise ValueError("min_bias can only be a list when performing \
            'calibration' run.")
        return min_bias
    return list(range(min_bias, max_bias + step, step))

