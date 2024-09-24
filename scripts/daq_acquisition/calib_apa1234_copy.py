import json, subprocess

calib_confs ={
              #'1_test':  {'mask_channel':[16,32,2], 'pulse_bias_percent_270nm': 4000, 'pulse_mode': "burst",  'pulse1_width_ticks': 5, 'burst_count': 6250},
              '12_0': {'channel_mask': 50, 'pulse_bias_percent_270nm': range(1200,3400,200), 'pulse1_width_ticks': 20},
              '34_0': {'channel_mask': 1,  'pulse_bias_percent_270nm': range(1400,2000,200), 'pulse1_width_ticks': 1},
              '34_1': {'channel_mask': 12, 'pulse_bias_percent_270nm': [2000,2200], 'pulse1_width_ticks': 1}
              }

#JSON EXAMPLE
data = {
    "modules": [
        {
            "data": {
                "card_id": 999,
                "board_id": 999,
                "module_id": 999,
                "interface_type": 1,
                "board_ip": "10.73.137.81",
                "partition_number": 0,
                "timing_address": 32,
                "number_channels": 12,
                "channel_mask": 1,
                "pulse_mode": "single",
                "pulse1_width_ticks": 1,
                "pulse_bias_percent_270nm": 4000,
                "hardware_configuration": [
                    {
                        "regname": "Literal",
                        "hexvalues": [
                            2147484776,
                            2147483648
                        ]
                    }
                ]
            },
            "match": "ssp_led_calib"
        }
    ]
}
# Run the configuration setup [seed, OV change, etc]
for ov in [1,2,3]:
    print("\nRunning seed command to change OV...")
        # subprocess.call(f"sh ",shell=True) # seed
    print("Running recreate_daphne_confs to apply changes...")
        # subprocess.call(f"sh ",shell=True)# recreate_daphne_confs      
    print(f"\n--- OV {ov} SET ---")
    # with open('np04daq-configs/SSP_CONFS/ssp_conf/data/ssp_conf.json') as f: data = json.load(f) # Load the template
    # Changing the pulse_bias_percent_270nm from 1350 to 1500
    for apa in calib_confs.keys():
        real_apa = apa.split("_")[0]
        print(f"\nRunning calibration for APA(s) {real_apa}")
        for intensity in calib_confs[apa]['pulse_bias_percent_270nm']:
            data['modules'][0]['data']['pulse_bias_percent_270nm'] = intensity 
            print(f"Running calibration for APA(s) {real_apa} with LED intensity set to {intensity}")                                                     
            for variable in calib_confs[apa].keys():
                if variable == 'pulse_bias_percent_270nm': continue #skip the mask_channel variable
                # Change the variable in the data
                data['modules'][0]['data'][variable] = calib_confs[apa][variable] 
                if data['modules'][0]['data']['pulse_mode'] == "single":
                    #remove burst_count from the json
                    try: data['modules'][0]['data'].pop('burst_count')
                    except KeyError: pass
            print(f"Config file:")
            print(data) 
            ## Write the modified data to a new file
            # with open(f'np04daq-configs/SSP_CONFS/ssp_conf/data/ssp_conf.json', 'w') as f: json.dump(data, f, indent=4) 
            ## Run the calibration acquisition
            # subprocess.call(f"sh run_calib.sh lperez {real_apa} 300 Calibration\ Run.\ Bias\ DCS:30V.\ Tests\ 270nm:\ SSP_config.\ channel_mask:{calib_confs[apa][channel_mask]},\ ticks_width:{calib_confs[apa][pulse1_width_ticks]},\ Pulse_bias_percent_270nm:{calib_confs[apa][pulse_bias_percent_270nm]} True",shell=True)          
