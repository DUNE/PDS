"""
Entry-point wrapper for an trim scan.

Usage:
    python -m pds.core.run_trim <conf.json>
"""
from __future__ import annotations
import sys
from pathlib import Path
from pds.core.run import main as run_main


def main(conf_path: str | Path | None = None) -> None:
    if conf_path is None:
        if len(sys.argv) < 2:
            print("Usage: python -m pds.core.run_trim <conf.json>")
            sys.exit(1)
        conf_path = sys.argv[1]
    run_main("trimscan", conf_path)

if __name__ == "__main__":
    main()
