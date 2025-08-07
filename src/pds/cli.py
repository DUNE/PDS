"""
Command-line entry point for PDS tooling.

* Adds --verbose / -v flag for DEBUG logging.
* Avoids double-initialising the root logger (Typer calls main() twice).
* Provides three sub-commands: run, seed, set.
"""

from __future__ import annotations
from logging.handlers import RotatingFileHandler
from pathlib import Path
import logging
from enum import Enum
from pathlib import Path

import typer

from pds.core import run, run_thr, run_att, seed, set_daphne_conf
from pds.core.run_thr import main as thr_main
from pds.core.run_att import main as att_main
from pds.core.run_offset import main as offset_main
from pds.core.run_trim import main as trim_main
from pds.core.utils import getlogfile
# ──────────────────────────────────────────────────────────────────────────────
# Typer app & mode enum
# ──────────────────────────────────────────────────────────────────────────────
class Mode(str, Enum):
    cosmics = "cosmics"
    noise = "noise"
    ledrun = "ledrun"
    calibrun = "calibrun"


app = typer.Typer(
    help="PDS Runner: Manage configurations and automation for the Photon Detection System (PDS)."
)

# ──────────────────────────────────────────────────────────────────────────────
# Sub-commands
# ──────────────────────────────────────────────────────────────────────────────
@app.command(name="run")
def run_command(
    mode: Mode = typer.Option(
        ...,
        "--mode",
        "-m",
        help="Type of run: cosmics, noise, ledrun, calibrun.",
    ),
    conf: Path = typer.Option(
        ...,
        "--conf",
        "-c",
        exists=True,
        readable=True,
        help="Path to conf JSON file.",
    ),
) -> None:
    """Launch a PDS data-acquisition run."""
    logging.info("🚀 Starting a PDS %s run using %s!", mode.value, conf)
    run.main(mode.value, conf)

@app.command("thr-scan")
def thr_scan(                     # ← name shown in `--help`
    conf: Path = typer.Argument(
        ...,
        exists=True,
        readable=True,
        help="Path to conf.json with mode='thrscan'",
    )
) -> None:
    """
    Iterate over correlation_threshold values defined in *conf* and
    take one run per setting.
    """
    thr_main(conf)


@app.command("att-scan")
def att_scan(                     # ← name shown in `--help`
    conf: Path = typer.Argument(
        ...,
        exists=True,
        readable=True,
        help="Path to conf.json with mode='attscan'",
    )
) -> None:
    """
    Iterate over attenuators values defined in *conf* and
    take one run per setting.
    """
    att_main(conf)

@app.command("offset-scan")
def offset_scan(                     # ← name shown in `--help`
    conf: Path = typer.Argument(
        ...,
        exists=True,
        readable=True,
        help="Path to conf.json with mode='offsetscan'",
    )
) -> None:
    """
    Iterate over offset values defined in *conf* and
    take one run per setting.
    """
    offset_main(conf)

@app.command("trim-scan")
def trimt_scan(                     # ← name shown in `--help`
    conf: Path = typer.Argument(
        ...,
        exists=True,
        readable=True,
        help="Path to conf.json with mode='trimscan'",
    )
) -> None:
    """
    Iterate over offset values defined in *conf* and
    take one run per setting.
    """
    trim_main(conf)

@app.command(name="seed")
def seed_command(
    details: Path = typer.Option(
        ...,
        "--details",
        "-d",
        exists=True,
        readable=True,
        help="Path to details JSON file.",
    )
) -> None:
    """Generate configuration files from details."""
    logging.info("🛠  Generating configuration files using %s!", details)
    seed.generate_seeds(details)


@app.command(name="set")
def set_command(
    conf: Path = typer.Option(
        ...,
        "--conf",
        "-c",
        exists=True,
        readable=True,
        help="Path to conf JSON file.",
    )
) -> None:
    """Apply configuration settings to hardware."""
    logging.info("🔧 Setting configuration using %s!", conf)
    set_daphne_conf.main(conf_path=conf)


# ──────────────────────────────────────────────────────────────────────────────
# Logging setup helper
# ──────────────────────────────────────────────────────────────────────────────
def _setup_logging(verbose: bool) -> None:
    """
    Configure the root logger exactly once.

    * Console output goes to stderr (as before).
    * A rotating log-file is written to ~/.pds/logs/pds-run.log
      ( ~5 MB per file, 3 backups ).
    """
    if logging.getLogger().handlers:
        return  # already configured (Typer calls main() twice)

    level = logging.DEBUG if verbose else logging.INFO
    fmt   = "%(asctime)s [%(levelname)s] %(message)s"

    # ── console handler (same as before) ───────────────────────────
    logging.basicConfig(level=level, format=fmt)

    # ── file handler ───────────────────────────────────────────────
    log_file = getlogfile()
    log_dir = log_file.parent
    log_dir.mkdir(parents=True, exist_ok=True)

    file_handler = RotatingFileHandler(
        log_file, maxBytes=5_000_000, backupCount=3
    )
    file_handler.setFormatter(logging.Formatter(fmt))
    file_handler.setLevel(level)
    logging.getLogger().addHandler(file_handler)

    if verbose:
        logging.debug(
            "Verbose mode enabled; logs also written to %s",
            log_file,
        )

# ──────────────────────────────────────────────────────────────────────────────
# Main entry
# ──────────────────────────────────────────────────────────────────────────────
def main(
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose (DEBUG) output."
    )
) -> None:
    _setup_logging(verbose)
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
