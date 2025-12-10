from __future__ import annotations

import logging
import subprocess
import time
from typing import Any

_LOG = logging.getLogger(__name__)


def _cfg_get(cfg: Any, key: str) -> Any:
    if isinstance(cfg, dict):
        return cfg.get(key)
    return getattr(cfg, key, None)


def generate_drunc_command(cfg: Any) -> str:
    change_rate = _cfg_get(cfg, "change_rate")
    wait_time = _cfg_get(cfg, "wait_time")
    oks_session = _cfg_get(cfg, "oks_session")
    session_name = _cfg_get(cfg, "session_name")
    drunc_target = _cfg_get(cfg, "drunc_target") or "main-np02-pds"

    if _cfg_get(cfg, "dry_run") or change_rate is None or wait_time is None or oks_session is None or session_name is None:
        return "echo '🧪 [dry-run] Simulating drunc command...'"
    return (
        "drunc-unified-shell ssh-CERN-kafka.json "
        f"{oks_session} {session_name} {drunc_target} "
        "start-run change-rate --trigger-rate "
        f"{change_rate} wait {wait_time} "
        "shutdown terminate"
    )


def run_drunc_command(cfg: Any, *, post_delay_s: int = 20) -> None:
    cmd = generate_drunc_command(cfg)
    if _cfg_get(cfg, "plan_only"):
        _LOG.info("plan_only=True; would run drunc command: %s", cmd)
        return
    if _cfg_get(cfg, "dry_run"):
        _LOG.info("🧪 Dry run: %s", cmd)
        return
    if "echo '" in cmd:
        _LOG.warning("⚠️  Missing drunc parameters (change_rate/wait_time/oks_session/session_name); skipping drunc. Command: %s", cmd)
        return
    _LOG.info("%s", cmd)
    subprocess.run(cmd, shell=True, cwd=cfg["drunc_working_dir"], check=True)
    _LOG.info("Sleeping for %s seconds. Press Ctrl+C if you need to stop...", post_delay_s)
    try:
        time.sleep(post_delay_s)
    except KeyboardInterrupt:
        _LOG.info("Interrupted by user.")
        raise
