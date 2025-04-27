import typer
import logging
from enum import Enum
from pathlib import Path
from pds.core import run, seed, set_daphne_conf

class Mode(str, Enum):
    cosmics = "cosmics"
    noise = "noise"
    calibration = "calibration"

app = typer.Typer(help="PDS Runner: Manage configurations and automation for the Photon Detection System (PDS).")

@app.command(name="run")
def run_command(
    mode: Mode = typer.Option(..., "--mode", "-m", help="Type of run: cosmics, noise, calibration."),
    conf: Path = typer.Option(..., "--conf", "-c", exists=True, readable=True, help="Path to conf JSON file.")
):
    """Launch a PDS data acquisition run."""
    logging.info(f"🚀 Starting a PDS {mode.value} run using {conf}!")
    run.main(mode.value, conf)

@app.command(name="seed")
def seed_command(
    details: Path = typer.Option(..., "--details", "-d", exists=True, readable=True, help="Path to details JSON file.")
):
    """Generate configuration files from details."""
    logging.info(f"🛠 Generating configuration files using {details}!")
    seed.main(details)

@app.command(name="set")
def set_command(
    conf: Path = typer.Option(..., "--conf", "-c", exists=True, readable=True, help="Path to conf JSON file.")
):
    """Apply configuration settings to hardware."""
    logging.info(f"🔧 Setting configuration using {conf}!")
    set_daphne_conf.main(conf)

def main(verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose (DEBUG) output.")):
    if verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(message)s")
        logging.debug("Verbose mode enabled.")
    else:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    app()
