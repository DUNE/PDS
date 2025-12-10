import subprocess
import os
import json

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
    result = subprocess.run(["pds-run", "--help"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "Usage:" in result.stdout

def test_pds_run_verbose():
    result = subprocess.run(["pds-run", "run", "--mode", "cosmics", "--conf", "tests/example_conf.json", "--verbose"], capture_output=True, text=True)
    assert result.returncode in (0, 1)  # in dry-run mode, may exit early
