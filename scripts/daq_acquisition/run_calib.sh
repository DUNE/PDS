#!/usr/bin/env bash

echo -e "\e[36m[INFO] Welcome to the script for acquiring \033[1mCALIBRATION RUNS!\033[0m"
echo -e "\e[36m To execute the script just run: \033[1msh run_calib.sh <username> <config_file> <runtime> <message> <expert_mode>\033[0m"
echo -e "\e[36m A log.txt file will be generated each time you run this script."
echo -e " If any of the arguments is missing, the script will ask for it."
echo -e " Enjoy! :) \n \e[0m"

# The confirmation message need to be run with $ bash setup.sh (this lines are to allow $ sh setup.sh too)
if [ ! "$BASH_VERSION" ] ; then
    exec /bin/bash "$0" "$@"
fi

# Check if the arguments are provided and if not ask for them
if [ -n "$1" ];then
    username=$1
    else
        read -p "Enter your username: " username
fi
if [ -n "$2" ];then
    config_file=$2
    else
        read -p "Enter the configuration file [np04_DAPHNE_APAs34_SSP.json]: " config_file
fi
if [ -n "$3" ];then
    runtime=$3
    else
        read -p "Enter the runtime in seconds [RECOMMENDED 180]: " runtime
fi
if [ -n "$4" ];then
    message=$4
    else
        read -p "Please enter a message to be added in the ELisA describing the run: " message
fi

# Look for the APAs in the filename and set the IPs accordingly
apas=${config_file#*_} # Get the last part of the filename after the first underscore
apas=${apas%_SSP.json} # Remove the SSP.json suffix
if [ "$apas" == "DAPHNE_APA1" ]; then
    your_ips=("4" "5" "7")
    your_apa="apa12"
fi
if [ "$apas" == "DAPHNE_APA2" ]; then
    your_ips=("9")
    your_apa="apa2"
fi
if [ "$apas" == "DAPHNE_APA3" ]; then
    your_ips=("11")
    your_apa="apa34"
fi
if [ "$apas" == "DAPHNE_APA4" ]; then
    your_ips=("12" "13")
    your_apa="apa34"
fi
if [ "$apas" == "DAPHNE_APAs34" ]; then
    your_ips=("11" "12" "13")
    your_apa="apa34"
fi

# Print the IPs and the Bias [V] for the user to confirm and save into the log file
log="pds_log/calib_log_$(date "+%F-%T").txt"
ip_string=$(IFS=,; echo "${your_ips[*]}")
echo -e "\n"
echo -e "You are going to acquire data with IPs: ($ip_string), which Bias [V] are: "
python /nfs/home/np04daq/daphne/daphne_interface/scripts/readV.py --ip_address $ip_string | tee -a $log

# Once all the arguments are set, ask for confirmation
if [ -n "$5" ] && [ "$5" = "True" ]; then
    echo "EXPERT_MODE ON: running without confirmation message"
else
    echo -e "\n"
    echo -e "\e[31mWARNING: You MUST be (in np04daq@np04-srv-024) inside \033[1mnp04_pds tmux!\033[0m\e[31m [tmux a -t np04_pds]\e[0m"
    echo -e "\e[31mCheck the endpoints are correctly setup and \033[1mbiased\033[0m\e[31m [careful with \033[1mnoise\033[0m\e[31m runs!]\e[0m"
    read -p "Are you sure you want to continue? (y/n) " -n 1 -r
    echo -e "\n"

    # If the user did not answer with y, exit the script
    if [[ ! $REPLY =~ ^[Yy]$ ]]
    then
        rm $log
        exit 1
    fi
fi

# Print the configuration and the command to be executed
echo "***** Running $config_file *****" | tee -a $log
echo "Running for $runtime seconds" | tee -a $log
echo "dtsbutler mst MASTER_PC059_1 align apply-delay 0 0 0 --force -m 3" | tee -a $log
echo "dtsbutler mst MASTER_PC059_1 faketrig-conf 0x7 0 1000" | tee -a $log
echo "nano04rc --partition-number 7 --timeout 120 global_configs/pds_calibration/${config_file} $username np04pds boot start_run --message "\"${message}\"" change_rate 10 wait ${runtime} stop_run" | tee -a $log
echo "==================================================" >> $log
echo "\nYOUR CONFIGURATION FOR DAPHNE:\n" >> $log
cat /nfs/home/np04daq/DAQ_NP04_HD_AREA/np04daq-configs/DAPHNE_CONFS/Calib_$your_apa/data/daphneapp_conf.json >> $log
echo "==================================================" >> $log

# Execute the commands
dtsbutler mst MASTER_PC059_1 align apply-delay 0 0 0 --force -m 3
dtsbutler mst MASTER_PC059_1 faketrig-conf 0x7 0 1000
nano04rc --partition-number 7 --timeout 120 global_configs/pds_calibration/${config_file} $username np04pds boot start_run --message "\"${message}\"" change_rate 10 wait ${runtime} stop_run

# Check if the commands were executed successfully
if [ $? -ne 0 ]; then
    echo "nanorc exited with errors!" | tee -a $log
    exit 1
fi

scp /nfs/home/np04daq/DAQ_NP04_HD_AREA/$log $username@lxplus.cern.ch:/eos/experiment/neutplatform/protodune/experiments/ProtoDUNE-II/PDS_Commissioning/log_files/.