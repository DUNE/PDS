import os
import json
import subprocess
import time

# Configuration
USERNAME = 'marroyav'  # Change to your username

CALIB_CONFS = {
    '1_0': {'channel_mask': 1, 'pulse_bias_percent_270nm': [1175, 1160, 1250, 1200], 'pulse1_width_ticks': 5}
}

RUNTIMES = {'1_0': 60}

DETAILS = ['Configuration_CB_20241209.json']
VGAIN = [1000, 1100, 1200, 1300, 1400, 1500, 1600, 1700, 1800, 1900, 2000, 2100, 2200, 2300, 2400, 2500, 2600, 2700, 2800, 2900]
BIAS_VECTORS = [
    [806, 0, 1200, 0, 0],
    [793, 0, 1187, 0, 0],
    [780, 0, 1174, 0, 0],
    [767, 0, 1161, 0, 0],
    [754, 0, 1148, 0, 0] ]

# Paths
BASE_DIR = "/nfs/sw/dunedaq/dunedaq-fddaq-v4.4.8-dev-vdcoldbox-dev"
CONF_DIR = os.path.join(BASE_DIR, "np04daq-configs")
DAPHNE_CONF_DIR = os.path.join(CONF_DIR, "DAPHNE_CONFS")
SSP_CONF_FILE = os.path.join(CONF_DIR, "SSP_CONFS/ssp_coldbox_conf/data/ssp_conf.json")

# Helper Functions
def run_command(command, cwd=None):
    """Run a shell command and ensure it succeeds."""
    try:
        print(f"Running command: {command}")
        result = subprocess.run(command, shell=True, cwd=cwd, check=True)
        return result.returncode
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {command}")
        print(f"Exit code: {e.returncode}")
        return e.returncode


def update_vgain(details, vgain):
    """Run the seed command to update VGAIN."""
    for detail in details:
        print(f"\nUpdating VGAIN to {vgain} for details file: {detail}")
        command = f"python cbseed -df {detail} -vg {vgain}"
        run_command(command, cwd=DAPHNE_CONF_DIR)
        print(f"Recreating DAPHNE configurations...")
        recreate_command = "./recreate_daphne_configurations.sh"
        run_command(recreate_command, cwd=CONF_DIR)


def update_bias_vector(details, bias_vector):
    """Overwrite the bias vector in the details configuration."""
    for detail in details:
        print(f"\nUpdating bias vector to {bias_vector} for details file: {detail}")
        details_path = os.path.join(DAPHNE_CONF_DIR, detail)

        # Read the details configuration file
        if not os.path.exists(details_path):
            print(f"Error: Details file not found: {details_path}")
            continue

        with open(details_path, 'r') as f:
            config = json.load(f)

        # Update the bias vector for all devices
        for device in config.keys():
            if device.startswith("10.73.137."):
                config[device]["bias"] = bias_vector

        # Write the updated configuration back
        with open(details_path, 'w') as f:
            json.dump(config, f, indent=4)

        print(f"Bias vector updated successfully in {detail}.")


def update_ssp_conf(apa, intensity, calib_confs):
    """Update the SSP configuration file."""
    print(f"Updating SSP configuration for APA: {apa}, Intensity: {intensity}")
    if not os.path.exists(SSP_CONF_FILE):
        print(f"Error: SSP configuration file not found: {SSP_CONF_FILE}")
        return False

    with open(SSP_CONF_FILE, 'r') as f:
        data = json.load(f)

    # Update the configuration
    data['modules'][0]['data']['pulse_bias_percent_270nm'] = intensity
    for variable, value in calib_confs[apa].items():
        if variable == 'pulse_bias_percent_270nm':
            continue
        data['modules'][0]['data'][variable] = value

    # Remove 'burst_count' if pulse_mode is 'single'
    if data['modules'][0]['data'].get('pulse_mode') == "single":
        data['modules'][0]['data'].pop('burst_count', None)

    # Write the updated configuration back
    with open(SSP_CONF_FILE, 'w') as f:
        json.dump(data, f, indent=4)

    print("SSP configuration updated successfully.")
    return True


def run_calibration(apa, intensity, runtime, vgain, bias_vector, details, expert_mode=True):
    """Run the calibration acquisition."""
    real_apa = apa.split("_")[0]
    print(f"Starting calibration for APA: {real_apa}, Intensity: {intensity}, Bias Vector: {bias_vector}")
    time.sleep(20)  # Simulate system wait time

    expert_flag = "True" if expert_mode else "False"
    command = (
        f"sh run_calib_cb.sh {USERNAME} {real_apa} {runtime} "
        f"\"Calibration Run. Bias DCS:30V. Tests 270nm: SSP_config. "
        f"channel_mask:{CALIB_CONFS[apa]['channel_mask']}, ticks_width:{CALIB_CONFS[apa]['pulse1_width_ticks']}, "
        f"Pulse_bias_percent_270nm:{intensity} VGAIN:{vgain} Bias_Vector:{bias_vector} {details}\" {expert_flag}"
    )
    result = run_command(command)
    if result != 0:
        print(f"Calibration for APA {real_apa} with Bias Vector {bias_vector} failed.")
    else:
        print(f"Calibration for APA {real_apa} with Bias Vector {bias_vector} completed successfully.")


# Main Execution
if __name__ == "__main__":
    for detail in DETAILS:
        for intensity in set([val for apa in CALIB_CONFS.values() for val in apa["pulse_bias_percent_270nm"]]):
            print(f"\nStarting scan with LED intensity: {intensity}")

            for bias_vector in BIAS_VECTORS:
                update_bias_vector([detail], bias_vector)

                for vgain in VGAIN:
                    update_vgain([detail], vgain)

                    for apa in CALIB_CONFS.keys():
                        if intensity in CALIB_CONFS[apa]['pulse_bias_percent_270nm']:
                            if update_ssp_conf(apa, intensity, CALIB_CONFS):
                                run_calibration(apa, intensity, RUNTIMES[apa], vgain, bias_vector, detail, expert_mode=True)

