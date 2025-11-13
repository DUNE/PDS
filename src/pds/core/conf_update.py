from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict, Mapping

from .utils import pretty_compact_json


def _coerce_value(value: str) -> Any:
    text = value.strip()
    lower = text.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    if lower == "null":
        return None
    try:
        return int(text, 0)
    except ValueError:
        try:
            return float(text)
        except ValueError:
            pass
    if (text.startswith("{") and text.endswith("}")) or (
        text.startswith("[") and text.endswith("]")
    ):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
    return text


def _set_nested(mapping: Dict[str, Any], dotted_key: str, value: Any) -> None:
    keys = dotted_key.split(".")
    target = mapping
    for key in keys[:-1]:
        if key not in target or not isinstance(target[key], dict):
            target[key] = {}
        target = target[key]
    target[keys[-1]] = value


def apply_updates(config: Dict[str, Any], updates: Mapping[str, str]) -> Dict[str, Any]:
    for key, raw_value in updates.items():
        if not key:
            raise ValueError("Empty key provided in updates")
        coerced = raw_value if not isinstance(raw_value, str) else _coerce_value(raw_value)
        _set_nested(config, key, coerced)
    return config


def update_conf_file(
    conf_path: Path,
    *,
    updates: Mapping[str, Any],
    output_path: Path | None = None,
    backup: bool = True,
    indent: int = 2,
) -> Path:
    if not conf_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {conf_path}")
    config_data = json.loads(conf_path.read_text())
    apply_updates(config_data, updates)

    destination = output_path or conf_path
    if backup and output_path is None:
        backup_path = conf_path.with_suffix(conf_path.suffix + ".bak")
        shutil.copy2(conf_path, backup_path)

    destination.write_text(
        pretty_compact_json(config_data, multiline=True, indent=indent)
    )
    return destination
