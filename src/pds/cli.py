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
from tempfile import NamedTemporaryFile
from typing import Any

import typer

from pds.core import run, run_thr, run_att, seed, set_daphne_conf
from pds.core.conf_update import update_conf_file
from pds.core.run_thr import main as thr_main
from pds.core.run_att import main as att_main
from pds.core.run_led import main as led_main
from pds.core.run_offset import main as offset_main
from pds.core.run_trim import main as trim_main
from pds.core.run_selftrigger import main as selfthr_main
from pds.core.run_afe_bias import main as afe_bias_main
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


def _parse_int_csv(value: str | None, *, option_name: str) -> list[int] | None:
    if value is None:
        return None
    items = [part.strip() for part in value.split(",") if part.strip()]
    if not items:
        raise typer.BadParameter(f"{option_name} cannot be empty.")
    try:
        return [int(item, 0) for item in items]
    except ValueError as exc:
        raise typer.BadParameter(f"{option_name} must be a comma-separated list of integers.") from exc

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
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable DEBUG logging.",
    ),
) -> None:
    """Launch a PDS data-acquisition run."""
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO)
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


@app.command("selfthr-scan")
def selfthr_scan(                     # ← name shown in `--help`
    conf: Path = typer.Argument(
        ...,
        exists=True,
        readable=True,
        help="Path to conf.json with mode='sthscan'",
    )
) -> None:
    """
    Iterate over self_trigger_threshold values defined in *conf* and
    take one run per setting.
    """
    selfthr_main(conf)


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

@app.command("led-calib-scan")
@app.command("led-intensity-scan")
def led_intensity_scan(
    conf: Path = typer.Argument(
        ...,
        exists=True,
        readable=True,
        help="Path to conf.json with mode='calibrun'",
    ),
    mask_values: str | None = typer.Option(
        None,
        "--mask-values",
        help="Comma-separated channel masks (for example: 1,2,4,8).",
    ),
    min_led_intensity: int | None = typer.Option(
        None,
        "--min-led-intensity",
        help="Lower LED intensity bound.",
    ),
    max_led_intensity: int | None = typer.Option(
        None,
        "--max-led-intensity",
        help="Upper LED intensity bound.",
    ),
    led_intensity_step: int | None = typer.Option(
        None,
        "--led-intensity-step",
        help="LED intensity scan step.",
    ),
    led_intensity_values: str | None = typer.Option(
        None,
        "--led-intensity-values",
        help="Comma-separated explicit LED intensities.",
    ),
) -> None:
    """
    Iterate over LED intensities and channel masks defined in *conf* and
    take one run per setting.
    """
    updates: dict[str, Any] = {}

    parsed_masks = _parse_int_csv(mask_values, option_name="--mask-values")
    if parsed_masks is not None:
        updates["scan.mask_values"] = parsed_masks

    parsed_led_values = _parse_int_csv(
        led_intensity_values,
        option_name="--led-intensity-values",
    )
    if parsed_led_values is not None:
        if any(value is not None for value in (min_led_intensity, max_led_intensity, led_intensity_step)):
            raise typer.BadParameter(
                "Use either --led-intensity-values or the min/max/step options, not both."
            )
        updates["scan.led_intensities.values"] = parsed_led_values
    else:
        if min_led_intensity is not None:
            updates["scan.led_intensities.min"] = min_led_intensity
        if max_led_intensity is not None:
            updates["scan.led_intensities.max"] = max_led_intensity
        if led_intensity_step is not None:
            updates["scan.led_intensities.step"] = led_intensity_step

    if not updates:
        led_main(conf)
        return

    with NamedTemporaryFile(
        mode="w",
        suffix=".json",
        dir=conf.parent,
        prefix=f".{conf.stem}.led-intensity.",
        delete=False,
    ) as tmp:
        tmp_path = Path(tmp.name)

    try:
        update_conf_file(
            conf_path=conf,
            updates=updates,
            output_path=tmp_path,
            backup=False,
            indent=2,
        )
        led_main(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)

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


@app.command("afe-bias-scan")
def afe_bias_scan(
    conf: Path = typer.Argument(
        ...,
        exists=True,
        readable=True,
        help="Path to conf.json with mode='afebiasscan'",
    )
) -> None:
    """
    Iterate over AFE v_bias values defined in *conf* and
    take one run per setting.
    """
    afe_bias_main(conf)

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


@app.command(name="conf-update")
def conf_update_command(
    conf: Path = typer.Option(
        ...,
        "--conf",
        "-c",
        exists=True,
        readable=True,
        help="Path to the base conf.json file.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Write the updated config to this path (defaults to in-place).",
    ),
    drunc_dir: Path | None = typer.Option(
        None,
        "--drunc-dir",
        help="Override drunc_working_dir.",
    ),
    daphne_details: str | None = typer.Option(
        None,
        "--daphne-details",
        help="Override daphne_details path.",
    ),
    oks_file: str | None = typer.Option(
        None,
        "--oks-file",
        help="Override oks_file path.",
    ),
    session_name: str | None = typer.Option(
        None,
        "--session-name",
        help="Override session_name.",
    ),
    daphne_obj: str | None = typer.Option(
        None,
        "--daphne-obj",
        help="Override daphne_obj.",
    ),
    mode: str | None = typer.Option(
        None,
        "--mode",
        help="Override run mode.",
    ),
    set_values: list[str] = typer.Option(
        [],
        "--set",
        "-s",
        help="Additional overrides (dotted.key=value). Repeat as needed.",
    ),
    backup: bool = typer.Option(
        True,
        "--backup/--no-backup",
        help="Keep a conf.json.bak when overwriting the input file.",
    ),
) -> None:
    """Patch conf.json fields without opening an editor."""
    updates: dict[str, Any] = {}
    if drunc_dir:
        updates["drunc_working_dir"] = str(drunc_dir)
    if daphne_details:
        updates["daphne_details"] = daphne_details
    if oks_file:
        updates["oks_file"] = oks_file
    if session_name:
        updates["session_name"] = session_name
    if daphne_obj:
        updates["daphne_obj"] = daphne_obj
    if mode:
        updates["mode"] = mode

    for assignment in set_values:
        if "=" not in assignment:
            raise typer.BadParameter(
                f"Invalid --set '{assignment}'. Expected format key=value."
            )
        key, value = assignment.split("=", 1)
        updates[key.strip()] = value.strip()

    if not updates:
        raise typer.BadParameter("Provide at least one override option or --set pair.")

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)

    updated_path = update_conf_file(
        conf_path=conf,
        updates=updates,
        output_path=output,
        backup=backup,
        indent=2,
    )
    logging.info("📝 Updated configuration written to %s", updated_path)


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
