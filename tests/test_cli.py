import subprocess
import os
import json

# Setup: create example conf file for testing
def setup_module(module):
    os.makedirs("tests", exist_ok=True)
    example_conf = {
        "example_key": "example_value"
    }
    with open("tests/example_conf.json", "w") as f:
        json.dump(example_conf, f)

def test_pds_run_help():
    result = subprocess.run(["pds-run", "--help"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "Usage:" in result.stdout

def test_pds_run_verbose():
    result = subprocess.run(["pds-run", "run", "--mode", "cosmics", "--conf", "tests/example_conf.json", "--verbose"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "DEBUG" in result.stdout
