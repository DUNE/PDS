from __future__ import annotations

import logging
import subprocess
import time
from typing import Any

_LOG = logging.getLogger(__name__)


def generate_drunc_command(cfg: dict[str, Any]) -> str:
    if cfg.get("dry_run"):
        return "echo '🧪 [dry-run] Simulating drunc command...'"
    return (
        "drunc-unified-shell ssh-CERN-kafka.json "
        f"{cfg['oks_session']} {cfg['session_name']} main-np02-pds "
        "start-run change-rate --trigger-rate "
        f"{cfg['change_rate']} wait {cfg['wait_time']} "
        "shutdown terminate"
    )


def run_drunc_command(cfg: dict[str, Any], *, post_delay_s: int = 20) -> None:
    cmd = generate_drunc_command(cfg)
    if cfg.get("dry_run"):
        _LOG.info("🧪 Dry run: %s", cmd)
        return
    _LOG.info("%s", cmd)
    subprocess.run(cmd, shell=True, cwd=cfg["drunc_working_dir"], check=True)
    _LOG.info("Sleeping for %s seconds. Press Ctrl+C if you need to stop...", post_delay_s)
    try:
        time.sleep(post_delay_s)
    except KeyboardInterrupt:
        _LOG.info("Interrupted by user.")
        raise
