import os, json, subprocess

username = 'lperez' # CHANGE THIS TO YOURS

# Run the configuration setup [seed, OV change, etc]
ov = "Vbd_best_20240709_complete_dic_FBK_4_5V_HPK_2_5V.json"    

for th in range(100,0,-5):
    print(f"\nRunning seed command to change OV...")
    print(f"python /nfs/home/np04daq/DAQ_NP04_HD_AREA/np04daq-configs/DAPHNE_CONFS/seed {ov}") # Execute seed
    os.chdir("/nfs/home/np04daq/DAQ_NP04_HD_AREA/np04daq-configs/DAPHNE_CONFS/")
    subprocess.call(f"python seed --details {ov} --threshold '{{ 4: 0, 5: 0, 10: 0, 9: {th}, 11: {th}, 12: {th}, 13: {th} }}'",shell=True) # Execute seed
    print("Running recreate_daphne_confs to apply changes...")
    os.chdir("/nfs/home/np04daq/DAQ_NP04_HD_AREA/np04daq-configs")
    print(f"./recreate_daphne_configurations.sh") # recreate_daphne_configurations      
    subprocess.call(f"./recreate_daphne_configurations.sh",shell=True) # recreate_daphne_configurations      
 
    print(f"\n--- {ov} + {th} DONE ---")
    os.chdir("/nfs/home/np04daq/DAQ_NP04_HD_AREA/")
    subprocess.call(f"sh run_cosmic.sh {username} 1234 80 Cosmic\ run.\ To\ test\ the\ threshold:{th}\ bandwidth\ value. True",shell=True)          
subprocess.call(f"scp /nfs/home/np04daq/DAQ_NP04_HD_AREA/pds_log/cosmic_log*.txt {username}@lxplus.cern.ch:/eos/experiment/neutplatform/protodune/experiments/ProtoDUNE-II/PDS_Commissioning/log_files/.",shell=True)
