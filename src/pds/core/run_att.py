"""
Entry-point wrapper for an attenuators scan.

Usage:
    python -m pds.core.run_att <conf.json>
"""
from __future__ import annotations
import sys
from pathlib import Path
from pds.core.run import main as run_main


def main(conf_path: str | Path | None = None) -> None:
    if conf_path is None:
        if len(sys.argv) < 2:
            print("Usage: python -m pds.core.run_att <conf.json>")
            sys.exit(1)
        conf_path = sys.argv[1]
    run_main("attscan", conf_path)


if __name__ == "__main__":
    main()