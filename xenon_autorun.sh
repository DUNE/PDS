#!/bin/bash

# This bash script will execute a python script, after it finishes, it will sleep for 15 minutes (or any time passed by the user) and then repeat the process indefinitely.
# If there is an error in the python script, it will print the error message and exit the loop.
# If it fails, it will send an email to the specified email address with the error message.

sleep_time=${1:-15m} # Default sleep time is 15 minutes if not provided as an argument

# Validate sleep_time format
if ! echo "$sleep_time" | grep -qE '^[0-9]+[smh]?$'; then
  echo "Invalid sleep_time format: '$sleep_time'. Use formats like 15m, 2h, 30s or plain seconds."
  (return 0 2>/dev/null) && return 1 || exit 1
fi

trap 'echo -e "\nInterrupted by user. Exiting."; exit 1' INT

basefile=./configs/np02/conf.json

conffile=./configs/np02/xeconf.json

jq '.verify_boot = true | .storage_type = "PROD" | .wait_time = 300' ${basefile} > ${conffile}
verify_boot=$(jq -r '.verify_boot' ${conffile})
if [ "$verify_boot" != "true" ]; then
    echo "verify_boot is not true, exiting."
    (return 0 2>/dev/null) && return 1 || exit 1
fi

countdown() {
    local duration=$1
    local seconds=$(echo $duration | awk '/m$/{print int($0)*60; next} /h$/{print int($0)*3600; next} /s$/{print int($0); next} {print int($0)}')
    
    while [ $seconds -gt 0 ]; do
        printf "\rNext run in: %02d:%02d:%02d - Press Ctrl-C to interrupt." $((seconds/3600)) $((seconds%3600/60)) $((seconds%60))
        sleep 1
        ((seconds--))
    done
    printf "\rNext run in: 00:00:00\n"
}

while true; do
  pds-run run -m cosmics -c ${conffile}
  if [ $? -ne 0 ]; then
    echo "Error occurred in your_script.py. Exiting loop."
    sendmail -v -i -t < mail_xedoping_warning.txt
    break
  fi
  sleep 2s
  countdown $sleep_time
done
