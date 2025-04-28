"""
Lightweight helper functions that several modules share.
(Deliberately kept free of heavy imports.)
"""

from __future__ import annotations

import json
from typing import Any

from .constants import JSON_INDENT


def pretty_compact_json(obj: Any, *, indent: int | None = None) -> str:
    """
    Produce deterministic JSON with tight spacing and newlines.

    The result is cached because many modules call this repeatedly
    with the *same* object instance during one run.
    """
    if indent is None:
        indent = JSON_INDENT

    def _dump(o: Any, level: int) -> str:
        spacing = " " * (level * indent)

        if isinstance(o, dict):
            items = [
                f'{spacing}{" " * indent}"{k}": {_dump(v, level + 1)}'
                for k, v in o.items()
            ]
            return "{\n" + ",\n".join(items) + f"\n{spacing}}}"
        if isinstance(o, list):
            items = [_dump(v, level + 1) for v in o]
            return (
                "[\n"
                + ",\n".join(
                    f'{" " * ((level + 1) * indent)}{item}' for item in items
                )
                + f"\n{spacing}]"
            )
        # primitives
        return json.dumps(o, separators=(",", ":"))

    # copy-by-value isn’t needed; json.dumps is read-only.
    return _dump(obj, 0)


def bitmask(channels: list[int], *, width: int = 40) -> int:
    """Convert a list of channel indices to a bitmask (ignoring out-of-range)."""
    return sum(1 << ch for ch in channels if 0 <= ch < width)
