import json, subprocess

with open('np04daq-configs/SSP_CONFS/ssp_conf/data/ssp_conf.json') as f: data = json.load(f) # Load the template
# width = data['modules'][0]['data']['pulse1_width_ticks'] 
width = 1

# Changing the pulse_bias_percent_270nm from 1350 to 1500
    for mask in [1,12]:
    for intensity in range(1400,2200,200):
        # Change the variable in the data
        data['modules'][0]['data']['pulse_bias_percent_270nm'] = intensity                           
        data['modules'][0]['data']['channel_mask'] = mask                           
        data['modules'][0]['data']['pulse1_width_ticks'] = width                           
        # Write the modified data to a new file
        with open(f'np04daq-configs/SSP_CONFS/ssp_conf/data/ssp_conf.json', 'w') as f: json.dump(data, f, indent=4) 
        # Run the calibration acquisition
        a = subprocess.call(f"sh run_calib.sh lperez 34 90 Calibration\ Run.\ Bias\ DCS:30V.\ Tests\ 270nm:\ SSP_config.\ mask_channel:1,\ ticks_width:1,\ Pulse_bias_percent_270nm:{i} True",shell=True)          
