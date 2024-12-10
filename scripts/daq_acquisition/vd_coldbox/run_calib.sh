#!/usr/bin/env bash

# Constants
LOG_DIR="pds_log"
CONFIG_FILE="global_configs/np02_coldbox_DAPHNE_SSP_ssh.json"
DEFAULT_HZ_TRIGGER="5500"
DEFAULT_DAQ_RATE="20"

# Colors
INFO="\e[36m"
WARN="\e[33m"
ERROR="\e[31m"
RESET="\e[0m"
BOLD="\033[1m"

# Helper Functions
print_info() {
    echo -e "${INFO}[INFO] $1${RESET}"
}

print_warn() {
    echo -e "${WARN}[WARNING] $1${RESET}"
}

print_error() {
    echo -e "${ERROR}[ERROR] $1${RESET}"
}

check_exit_code() {
    if [ $? -ne 0 ]; then
        print_error "$1"
        exit 1
    fi
}

# Welcome Message
print_info "Welcome to the Calibration Runs Script!"
echo -e "${INFO}To execute the script: ${BOLD}sh run_calib_cb.sh <username> <apa_number> <runtime> <message> <expert_mode>${RESET}"
echo -e "${INFO}A log.txt file will be generated each time you run this script.\n${RESET}"

# Enforce Bash
if [ ! "$BASH_VERSION" ]; then
    exec /bin/bash "$0" "$@"
fi

# Arguments
if [ -n "$1" ]; then
    username=$1
else
    read -p "Enter your username: " username
fi

if [ -n "$2" ]; then
    apa_number=$2
else
    read -p "Enter the APA number(s) you want to acquire [34]: " apa_number
fi

if [ -n "$3" ]; then
    runtime=$3
else
    read -p "Enter the runtime in seconds [RECOMMENDED 180]: " runtime
fi

if [ -n "$4" ]; then
    message=$4
else
    read -p "Enter a message to describe the run: " message
fi

expert_mode=${5:-False}

# Log Setup
log_file="${LOG_DIR}/calib_log_$(date "+%F-%T").txt"
mkdir -p "${LOG_DIR}"

print_info "Log file will be saved to ${log_file}"
config_file="${CONFIG_FILE}"

if [ ! -f "${config_file}" ]; then
    print_error "Configuration file ${config_file} not found!"
    exit 1
fi

# Print Configuration Details
print_info "Using configuration file: ${config_file}"
cat "${config_file}" >> "${log_file}"

print_info "TRIGGER_AD-HOC (0x7) is set to ${DEFAULT_HZ_TRIGGER} Hz"
echo -e "nano04rc --partition-number 3 --timeout 120 ${config_file} ${username} np02vdcoldbox boot start_run --message \"${message}\" change_rate ${DEFAULT_DAQ_RATE} wait ${runtime} stop_run" >> "${log_file}"

# Confirmation (if not expert mode)
if [ "${expert_mode}" != "True" ]; then
    print_warn "Make sure you are in the np04_pds tmux session! [tmux a -t np04_pds]"
    read -p "Are you sure you want to continue? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_error "User aborted the script."
        exit 1
    fi
fi

# Run Calibration
print_info "Running calibration for APA ${apa_number} with runtime ${runtime} seconds."
dtsbutler mst BOREAS_TLU_NP04 align apply-delay 0 0 0 --force -m 3
check_exit_code "Failed to apply alignment delay."

dtsbutler mst BOREAS_TLU_NP04 faketrig-conf 0x7 0 ${DEFAULT_HZ_TRIGGER}
check_exit_code "Failed to configure faketrig."

nano04rc --partition-number 6 --timeout 120 "${config_file}" "${username}" np02vdcoldbox boot start_run --message "\"${message}\"" change_rate "${DEFAULT_DAQ_RATE}" wait "${runtime}" stop_run
check_exit_code "Failed to execute nano04rc commands."

# Log Transfer (if not expert mode)
if [ "${expert_mode}" != "True" ]; then
    print_info "Transferring log file to EOS..."
    scp "${log_file}" "${username}@lxplus.cern.ch:/eos/experiment/neutplatform/protodune/experiments/ProtoDUNE-II/PDS_Commissioning/log_files/"
    check_exit_code "Failed to transfer log file to EOS."
fi

print_info "Calibration run completed successfully!"

