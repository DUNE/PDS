from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


_LOG = logging.getLogger(__name__)


@dataclass
class DTSButler:
    workdir: Path
    align_cmd: str = ""
    fake_cmd_tpl: str = ""
    clear_cmd: str = ""
    mode: str = ""
    skip: bool = False

    def run(self, *, hztrigger: Optional[float] = None) -> None:
        align_command = ["bash", "-c", f"cd {self.workdir} && {self.align_cmd}"]
        if self.skip:
            _LOG.info("  Skipping Butler alignment (skip_dts=True)...")
            _LOG.info(f"  Aligment command: {' '.join(align_command)}")
            return

        if self.mode in ("cosmics", "thrscan", "threshold", "sthscan", "selftrigger"):
            _LOG.warning("⚠️  %s run – skipping DTS alignment.", self.mode)
            self.clear()
            return

        if self.align_cmd.strip():
            _LOG.info("📢  DTS alignment …")
            subprocess.run(align_command, check=True)


        if hztrigger is not None and self.fake_cmd_tpl.strip():
            cmd = self.fake_cmd_tpl.format(hztrigger=hztrigger)
            subprocess.run(["bash", "-c", f"cd {self.workdir} && {cmd}"], check=True)
            _LOG.info("✅  DTS fake-trigger configured.")

    def clear(self) -> None:
        if self.skip:
            _LOG.info("  Skipping Butler clear (skip_dts=True)...")
            return
        if not self.clear_cmd.strip():
            _LOG.info("  Skipping Butler clear (no clear command provided)...")
            return
        subprocess.run(["bash", "-c", f"cd {self.workdir} && {self.clear_cmd}"], check=False)
