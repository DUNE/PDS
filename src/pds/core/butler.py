from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from typing import Optional


_LOG = logging.getLogger(__name__)


@dataclass
class DTSButler:
    align_cmd: list[str]
    fake_cmd_tpl: list[str]
    clear_cmd: list[str]
    mode: str
    skip: bool = False

    def run(self, *, hztrigger: Optional[float] = None) -> None:
        if self.skip:
            _LOG.info("  Skipping Butler alignment (skip_dts=True)...")
            return

        if self.mode in ("cosmics", "thrscan", "threshold", "sthscan", "selftrigger"):
            _LOG.warning("⚠️  %s run – skipping DTS alignment.", self.mode)
            self.clear()
            return

        _LOG.info("📢  DTS alignment …")
        subprocess.run(self.align_cmd, check=True)

        if hztrigger is not None and self.fake_cmd_tpl:
            cmd = self.fake_cmd_tpl.copy()
            cmd[-1] = cmd[-1].format(hztrigger=hztrigger)
            subprocess.run(cmd, check=True)
            _LOG.info("✅  DTS fake-trigger configured.")

    def clear(self) -> None:
        if self.skip:
            _LOG.info("  Skipping Butler clear (skip_dts=True)...")
            return
        subprocess.run(self.clear_cmd, check=False)
