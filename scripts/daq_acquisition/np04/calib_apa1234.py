import json, subprocess

username = 'lperez' # CHANGE THIS TO YOURS

calib_confs = {
              '1_0':  {'channel_mask': 50, 'pulse_bias_percent_270nm': [1400,1800,2200,2800], 'pulse1_width_ticks': 20},
              '2_0':  {'channel_mask': 50, 'pulse_bias_percent_270nm': [1400,1800,2200,2800,3400,4000], 'pulse1_width_ticks': 20},
              '34_0': {'channel_mask': 1,  'pulse_bias_percent_270nm': [1400,1600,1800], 'pulse1_width_ticks': 1},
              '34_1': {'channel_mask': 12, 'pulse_bias_percent_270nm': [2000,2200], 'pulse1_width_ticks': 1}
              }

runtime = {
            '1_0':  240, #0x7 command to 50
            '2_0':  180, #0x7 command to 6250
            '34_0': 180, #0x7 command to 6250
            '34_1': 180, #0x7 command to 6250
          }

# Run the configuration setup [seed, OV change, etc]
OV = [
      "Vbd_best_20240709_complete_dic_FBK_3_5V_HPK_2_0V.json",
      "Vbd_best_20240709_complete_dic_FBK_4_5V_HPK_2_5V.json",
      "Vbd_best_20240709_complete_dic_FBK_7_0V_HPK_3_0V.json",
     ]

for ov in OV:
    print(f"\nRunning seed command to change OV...")
    print(f"python /nfs/home/np04daq/DAQ_NP04_HD_AREA/np04daq-configs/DAPHNE_CONFS/seed {ov}") # Execute seed
    os.chdir("np04daq-configs/DAPHNE_CONFS/")
    subprocess.call(f"python seed --details {ov}",shell=True) # Execute seed
    print("Running recreate_daphne_confs to apply changes...")
    os.chdir("..")
    print(f"./recreate_daphne_configurations.sh") # recreate_daphne_configurations      
    subprocess.call(f"./recreate_daphne_configurations.sh",shell=True) # recreate_daphne_configurations      
 
    print(f"\n--- {ov} DONE ---")
    
    with open('np04daq-configs/SSP_CONFS/ssp_conf/data/ssp_conf.json') as f: data = json.load(f) # Load the template
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
            # Write the modified data to a new file
            with open(f'np04daq-configs/SSP_CONFS/ssp_conf/data/ssp_conf.json', 'w') as f: json.dump(data, f, indent=4) 
            # Run the calibration acquisition
            subprocess.call(f"sh run_calib.sh {username} {real_apa} {runtime} Calibration\ Run.\ Bias\ DCS:30V.\ Tests\ 270nm:\ SSP_config.\ channel_mask:{calib_confs[apa]['channel_mask']},\ ticks_width:{calib_confs[apa]['pulse1_width_ticks']},\ Pulse_bias_percent_270nm:{intensity} True",shell=True)          
            
subprocess.call(f"scp /nfs/home/np04daq/DAQ_NP04_HD_AREA/pds_log/calib_log*.txt {username}@lxplus.cern.ch:/eos/experiment/neutplatform/protodune/experiments/ProtoDUNE-II/PDS_Commissioning/log_files/.",shell=True)
