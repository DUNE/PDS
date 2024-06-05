#!/usr/bin/env bash

echo -e "\e[36m[INFO] Welcome to the script for acquiring \033[1mCOSMICS RUNS!\033[0m"
echo -e "\e[36m To execute the script just run: \033[1msh run_cosmic.sh <username> <apa_number> <runtime> <message> <expert_mode>\033[0m"
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
    apa_number=$2
    else
        # read -p "Enter the configuration file [np04_DAPHNE_APAs34.json]: " apa_number
        read -p "Enter the the apas you want to acquire [34]: " apa_number
fi
if [ -n "$3" ];then
    runtime=$3
    else
        read -p "Enter the runtime in seconds [RECOMMENDED 600]: " runtime
fi
if [ -n "$4" ];then
    message=$4
    else
        read -p "Please enter a message to be added in the ELisA describing the run: " message
fi

# Look for the APAs in the filename and set the IPs accordingly
# apas=${config_file#*_} # Get the last part of the filename after the first underscore
# your_apa=($(echo $apas | grep -o -E '[0-9]+')) # Get the numbers from the name

declare -A apa_map
apa_map[1]="4 5 7"
apa_map[2]="9"
apa_map[3]="11"
apa_map[4]="12 13"

your_ips=()
for apa in $(echo $apa_number | fold -w1); do
    your_ips+=(${apa_map[$apa]})
done
ip_string=$(IFS=,; echo "${your_ips[*]}")

log="pds_log/cosmic_log_$(date "+%F-%T").txt"
config_file=global_configs/pds_cosmics/np04_DAPHNE_APAs${apa_number}.json

echo -e "\e[32m\nYou selected APA(s) ($apa_number) with enpoints ($ip_string) !\e[0m"
echo -e "\e[35mWe are going to use $config_file if exists :) \e[0m"

## Reading bias deprecated. To be deleted
# # Print the IPs and the Bias [V] for the user to confirm and save into the log file
# # echo -e "You are going to acquire data with IPs: ($ip_string), which Bias [V] are: "
# # python /nfs/home/np04daq/daphne/daphne_interface/scripts/readV.py --ip_address $ip_string | tee -a $log

# Once all the arguments are set, ask for confirmation
if [ -n "$5" ] && [ "$5" = "True" ]; then
    echo "EXPERT_MODE ON: running without confirmation message"
else
    echo -e "\e[33mWARNING: You MUST be (in np04daq@np04-srv-024) inside \033[1mnp04_pds tmux!\033[0m \e[33m[tmux a -t np04_pds]\e[0m"
    # echo -e "\e[31mCheck the endpoints are correctly setup and \033[1mbiased\033[0m\e[31m [careful with \033[1mnoise\033[0m\e[31m runs!]\e[0m"
    echo -e "\n"
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
echo -e "***** Running $config_file *****" | tee -a $log
cat $config_file >> $log
echo -e "\nRunning for $runtime seconds" | tee -a $log
echo -e "dtsbutler mst MASTER_PC059_1 align apply-delay 0 0 0 --force -m 3" | tee -a $log
echo -e "dtsbutler mst MASTER_PC059_1 faketrig-clear 0" | tee -a $log
echo -e "nano04rc --partition-number 7 --timeout 120 $config_file $username np04pds boot start_run --message "\"${message}\"" change_rate 10 wait ${runtime} stop_run" | tee -a $log
echo -e "==================================================" >> $log
echo -e "\nYOUR CONFIGURATION FOR DAPHNE:\n" >> $log
cat /nfs/home/np04daq/DAQ_NP04_HD_AREA/np04daq-configs/DAPHNE_CONFS/Cosmics_apa$apa_number/data/daphneapp_conf.json >> $log
echo -e "==================================================" >> $log

# Execute the commands
dtsbutler mst MASTER_PC059_1 align apply-delay 0 0 0 --force -m 3
dtsbutler mst MASTER_PC059_1 faketrig-clear 0
nano04rc --partition-number 7 --timeout 120 ${config_file} $username np04pds boot start_run --message "\"${message}\"" change_rate 10 wait ${runtime} stop_run

# Check if the commands were executed successfully
if [ $? -ne 0 ]; then
    echo "nanorc exited with errors!" | tee -a $log
    exit 1
fi

scp /nfs/home/np04daq/DAQ_NP04_HD_AREA/$log $username@lxplus.cern.ch:/eos/experiment/neutplatform/protodune/experiments/ProtoDUNE-II/PDS_Commissioning/log_files/.