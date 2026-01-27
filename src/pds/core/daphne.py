from __future__ import annotations

import json
import logging
import subprocess
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Dict, Tuple

from .config_model import BaseScanConfig

_LOG = logging.getLogger(__name__)


def _diff(before: Dict[str, Any], after: Dict[str, Any], prefix: str = "") -> Dict[str, Tuple[Any, Any]]:
    """Return a flat dict of changed leaves: key -> (old, new)."""
    changes: Dict[str, Tuple[Any, Any]] = {}
    keys = set(before.keys()) | set(after.keys())
    for key in keys:
        b = before.get(key)
        a = after.get(key)
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(b, dict) and isinstance(a, dict):
            changes.update(_diff(b, a, path))
        elif b != a:
            changes[path] = (b, a)
    return changes


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=False))


def apply_daphne_patch(
    cfg: BaseScanConfig,
    *,
    details_path: Path,
    xml_path: Path,
    tmp_dir: Path,
    mutate: Callable[[Dict[str, Any]], None],
    description: str,
    timeout_ms: int = 5000,
    current_state: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Apply a minimal patch to the DAPHNE object and return the new state."""
    obj_name = cfg.daphne_obj
    if not obj_name:
        raise ValueError("daphne_obj must be provided to update the DAPHNE configuration.")

    if current_state is not None:
        baseline = deepcopy(current_state)
    else:
        if not details_path.exists():
            raise FileNotFoundError(f"Daphne details file does not exist at {details_path}")
        baseline = json.loads(details_path.read_text())

    if not xml_path.exists():
        raise FileNotFoundError(f"XML file does not exist at {xml_path}")

    desired = deepcopy(baseline)
    mutate(desired)

    changes = _diff(baseline, desired)
    if not changes:
        _LOG.info("No DAPHNE changes required for %s. Writting it any wait because I don't know the state of the xml", description)
        # Removed the return for now...
        # return desired

    _LOG.info("Planned DAPHNE changes for %s:", description)
    for key, (old, new) in changes.items():
        _LOG.info("  %s: %s -> %s", key, old, new)

    if cfg.plan_only:
        _LOG.info("plan_only=True; skipping DAPHNE update.")
        return desired

    # Keep only board entries (numeric keys) to satisfy add_daphne_conf expectations.
    cleaned = {k: v for k, v in desired.items() if isinstance(k, str) and k.isdigit()}
    if not cleaned:
        # Trying to generate a seed... 
        tmp_json_seed = tmp_dir / f"{obj_name}_daphne_patch_seed.json"
        _write_json(tmp_json_seed, desired )
        cmd = [
            "pds-run",
            "seed",
            "-d",
            str(tmp_json_seed),
            "-o",
            str(tmp_json_seed.parent)
            ]
        _LOG.info("📢 Running pds-run seed update command: %s", " ".join(cmd))
        subprocess.run(cmd, check=True)

        with open(Path(tmp_json_seed.parent/"np02_daphne_selftrigger.json"), 'r') as file:
            cleaned = json.load(file)
            
    tmp_json = tmp_dir / f"{obj_name}_daphne_patch.json"
    _write_json(tmp_json, cleaned)

    cmd = [
        "add_daphne_conf",
        str(xml_path),
        str(tmp_json),
        "-n",
        obj_name,
        "-t",
        str(timeout_ms),
    ]
    _LOG.info("📢 Running XML update command: %s", " ".join(cmd))
    subprocess.run(cmd, check=True)

    return desired
