import json, subprocess

with open('np04daq-configs/SSP_CONFS/ssp_conf/data/ssp_conf.json') as f: data = json.load(f) # Load the template
# Changing the pulse_bias_percent_270nm from 1350 to 1500
width = data['modules'][0]['data']['pulse1_width_ticks'] 
for variable in ['pulse_bias_percent_270nm']:
    for i in range(100,67,-3):
    # for i in range(1350,1500,10):
        # Change the variable in the data
        data['modules'][0]['data'][variable] = i                            
        # Write the modified data to a new file
        with open(f'np04daq-configs/SSP_CONFS/ssp_conf/data/ssp_conf.json', 'w') as f: json.dump(data, f, indent=4) 
        # Run the calibration acquisition
        a = subprocess.call(f"sh run_calib.sh lperez np04_DAPHNE_APAs34_SSP.json 90 Calibration\ Run.\ Bias\ DCS:15V.\ Tests\ 270nm:SSP_config.\ Pulse_bias_percent_270nm:{i} True",shell=True)          
