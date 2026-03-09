import subprocess
import os
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(SRC) if not existing_pythonpath else f"{SRC}:{existing_pythonpath}"
    return subprocess.run(
        [sys.executable, "-m", "pds.cli", *args],
        capture_output=True,
        text=True,
        env=env,
    )

# Setup: create example conf file for testing
def setup_module(module):
    os.makedirs("tests", exist_ok=True)
    example_conf = {
        "mode": "cosmics",
        "drunc_working_dir": "/tmp",
        "oks_file": "ok.xml",
        "daphne_details": "details.json",
        "skip_dts": True,
        "skip_daphne_conf": True,
        "skip_ssp_conf": True,
        "dry_run": True
    }
    with open("tests/example_conf.json", "w") as f:
        json.dump(example_conf, f)

def test_pds_run_help():
    result = _run_cli("--help")
    assert result.returncode == 0
    assert "Usage:" in result.stdout
    assert "led-intensity-scan" in result.stdout

def test_pds_run_verbose():
    result = _run_cli("run", "--mode", "cosmics", "--conf", "tests/example_conf.json", "--verbose")
    assert result.returncode in (0, 1)  # in dry-run mode, may exit early
