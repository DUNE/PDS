#!/usr/bin/env python3

import subprocess
import sys
import argparse

# Define the location of the OKS file
OKS_FILE = "/nfs/home/marroyav/fddaq-v5.2.1-a9/ehn1-daqconfigs/segments/np02-pds.data.xml"

# Define the drunc-unified-shell command
DRUNC_CMD = (
    "drunc-unified-shell ssh-standalone "
    "ehn1-daqconfigs/sessions/np02-session.data.xml np02-session "
    "boot conf start enable-triggers change-rate 2. wait 40 "
    "disable-triggers drain-dataflow stop-trigger-sources stop scrap terminate"
)

class WebProxy:
    """Handles sourcing the web proxy at the beginning of execution."""
    
    WEB_PROXY_CMD = "source ~np04daq/bin/web_proxy.sh -u"
    
    @staticmethod
    def setup():
        """Sources the web proxy script."""
        print("\n=== Sourcing web_proxy.sh ===")
        result = subprocess.call(f"bash -c '{WebProxy.WEB_PROXY_CMD}'", shell=True)
        if result != 0:
            print("\nError: Failed to source web_proxy.sh")
            sys.exit(1)

class DTSButler:
    """Handles the execution of DTS commands."""
    
    DTS_ALIGN_CMD = "dtsbutler mst MASTER_PC059_1 align apply-delay 0 0 0 --force -m 3"
    DTS_FAKETRIG_CMD_TEMPLATE = "dtsbutler mst MASTER_PC059_1 faketrig-conf 0x7 0 {hztrigger}"

    def __init__(self, hztrigger):
        self.hztrigger = hztrigger

    def run(self):
        """Runs DTS alignment and fake trigger configuration."""
        print("\n=== Running DTS Alignment Command ===")
        result = subprocess.call(DTSButler.DTS_ALIGN_CMD, shell=True)
        if result != 0:
            print("\nError: DTS alignment command failed.")
            sys.exit(1)

        dts_faketrig_cmd = DTSButler.DTS_FAKETRIG_CMD_TEMPLATE.format(hztrigger=self.hztrigger)
        print(f"\n=== Running DTS Fake Trigger Command: {dts_faketrig_cmd} ===")
        result = subprocess.call(dts_faketrig_cmd, shell=True)
        if result != 0:
            print("\nError: DTS fake trigger command failed.")
            sys.exit(1)

def run_set_ssp_conf(oksfile, **kwargs):
    """Runs the set_ssp_conf script with the provided arguments."""
    cmd = ["set_ssp_conf", oksfile]  # Base command
    
    for key, value in kwargs.items():
        if value is not None:
            option = f"--{key.replace('_', '-')}"  # Convert Python-style names to CLI format
            cmd.append(option)
            cmd.append(str(value))

    try:
        result = subprocess.run(cmd, check=True, text=True, capture_output=True)
        print(f"\n=== Running set_ssp_conf with {kwargs} ===")
        print("Output:\n", result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"\nError running set_ssp_conf with {kwargs}:")
        print("stderr:", e.stderr)
        sys.exit(1)

def run_drunc_command():
    """Runs the drunc-unified-shell command."""
    print("\n=== Running drunc-unified-shell sequence ===")
    result = subprocess.call(DRUNC_CMD, shell=True)
    if result != 0:
        print("\nError: drunc-unified-shell command failed.")
        sys.exit(1)

class MaskTest:
    """Iterates over different channel masks to test the response."""
    
    def __init__(self, mask_values=None):
        if mask_values is None:
            mask_values = [1, 2, 4, 8, 16, 32]  # Default values
        self.mask_values = mask_values

    def run(self):
        """Iterates over channel masks and runs set_ssp_conf."""
        for mask in self.mask_values:
            run_set_ssp_conf(
                oksfile=OKS_FILE,
                object_name="np02-ssp-on",
                number_channels=12,
                channel_mask=mask,
                pulse_mode="single",
                burst_count=1,
                double_pulse_delay_ticks=0,
                pulse1_width_ticks=5,
                pulse2_width_ticks=0,
                pulse_bias_percent_270nm=4000,
                pulse_bias_percent_367nm=0
            )
            run_drunc_command()

class PulseBiasTest:
    """Iterates over pulse_bias_percent_270nm in steps of 500."""
    
    def __init__(self, min_bias=0, max_bias=4000, step=500):
        self.min_bias = min_bias
        self.max_bias = max_bias
        self.step = step

    def run(self):
        """Iterates over pulse_bias_percent_270nm and runs set_ssp_conf."""
        for bias in range(self.min_bias, self.max_bias + self.step, self.step):
            run_set_ssp_conf(
                oksfile=OKS_FILE,
                object_name="np02-ssp-on",
                number_channels=12,
                channel_mask=0xFFF,  # Default mask (can be adjusted)
                pulse_mode="single",
                burst_count=1,
                double_pulse_delay_ticks=0,
                pulse1_width_ticks=5,
                pulse2_width_ticks=0,
                pulse_bias_percent_270nm=bias,
                pulse_bias_percent_367nm=0
            )
            run_drunc_command()

if __name__ == "__main__":
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Run either the Mask Test or the Pulse Bias Test.")
    parser.add_argument("--test", choices=["mask", "intensity"], required=True,
                        help="Choose whether to run the 'mask' test or the 'intensity' (pulse bias) test.")
    parser.add_argument("--hztrigger", type=int, default=1000,
                        help="Set the Hz trigger for faketrig-conf (default: 1000).")
    
    args = parser.parse_args()

    # Setup Web Proxy
    WebProxy.setup()

    # Setup and run DTSButler
    dtsbutler = DTSButler(args.hztrigger)
    dtsbutler.run()

    # Execute the selected test
    if args.test == "mask":
        print("\n=== Running MASK TEST ===")
        mask_test = MaskTest()
        mask_test.run()
    elif args.test == "intensity":
        print("\n=== Running PULSE INTENSITY TEST ===")
        pulse_bias_test = PulseBiasTest()
        pulse_bias_test.run()