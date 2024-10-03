#!/usr/bin/env python3
# PATH: /nfs/sw/dunedaq/dunedaq-fddaq-v4.4.3/np04daq-configs/DAPHNE_CONFS

import json


with open("/afs/cern.ch/user/a/anbalbon/IV_curve/PDS/data/iv_analysis/Vbd_best_20240705/Vbd_best_20240705_complete_dic_FBK(-0,5V)_HPK(-0,5V).json", 'r') as f:
   
    map = json.load(f)

confs = {
    "ALL": [4, 5, 7, 9, 11, 12, 13],
    "APA1": [4, 5, 7],
    "APA2": [9],
    "APA3": [11],
    "APA4": [12, 13],
    "APAs12": [4, 5, 7, 9],
    "APAs34": [11, 12, 13],
    "APAs124": [4, 5, 7, 9, 12, 13]
}

threshold_calib = {
    4: 0,
    5: 0,
    7: 0,
    9: 15000,
    11: 15000,
    12: 15000,
    13: 15000
}

threshold_cosmics = {
    4: 0,
    5: 0,
    7: 0,
    9: 20,
    11: 20,
    12: 20,
    13: 20
}

for dev in confs.keys():
    endpoints = confs[dev]
    #threshold = (15000)
    order = [0, 2, 5, 7, 1, 3, 4, 6, 8, 10, 13, 15,
             9, 11, 12, 14, 16, 18, 21, 23, 17, 19, 20, 22]
    details = {"details":
               [{"id": i, "value":
                {"self_trigger_threshold": threshold_calib[i],
                 "full_stream_channels": sorted(map[f'10.73.137.{100+i}']['ch'], key=order.index) if i < 8 else [],
                 "channels": {
                     "gains": [{"id": j, "value": 1} for j in map[f'10.73.137.{100+i}']["ch"]],
                     "offsets": [{"id": j, "value": 2200} for j in map[f'10.73.137.{100+i}']["ch"]],
                     "trims": [{"id": j, "value": trim} for j,trim in enumerate(map[f'10.73.137.{100+i}']["trim"]) if trim !=0]},
                 "afes": {
                     "v_gains": [{"id": afe, "value": 2318} for afe in range(5)],
                     "v_biases": [{"id": afe, "value": biasv} for afe, biasv in enumerate(map[f'10.73.137.{100+i}']["bias"])],
                     "adcs": [{"id": afe, "value": {"resolution": 0, "output_format": 1, "SB_first": 1}}for afe in range(5)],
                     "pgas": [{"id": afe, "value": {"lpf_cut_frequnecy": 0, "integrator_disable": 0, "gain": 0}}for afe in range(5)],
                     "lnas": [{"id": afe, "value": {"clamp": 0, "integrator_disable": 0, "gain": 2}}for afe in range(5)]}
                 }
                 } for i in endpoints]}

    print(json.dumps(details, sort_keys=True, indent=4))
    with open(f'np04_daphne_{dev}_calib_seed.json', "w") as outfile:
        json.dump(details, outfile, indent=4)
    #threshold = 150
    details = {"details":
               [{"id": i, "value":
                {"self_trigger_threshold": threshold_cosmics[i],
                 "full_stream_channels": sorted(map[f'10.73.137.{100+i}']['ch'], key=order.index) if i < 8 else [],
                 "channels": {
                     "gains": [{"id": j, "value": 1} for j in map[f'10.73.137.{100+i}']["ch"]],
                     "offsets": [{"id": j, "value": 2200} for j in map[f'10.73.137.{100+i}']["ch"]],
                     "trims": [{"id": j, "value": trim} for j,trim in enumerate(map[f'10.73.137.{100+i}']["trim"]) if trim !=0]},
                 "afes": {
                     "v_gains": [{"id": afe, "value": 2318} for afe in range(5)],
                     "v_biases": [{"id": afe, "value": biasv} for afe, biasv in enumerate(map[f'10.73.137.{100+i}']["bias"])],
                     "adcs": [{"id": afe, "value": {"resolution": 0, "output_format": 1, "SB_first": 1}}for afe in range(5)],
                     "pgas": [{"id": afe, "value": {"lpf_cut_frequnecy": 0, "integrator_disable": 0, "gain": 0}}for afe in range(5)],
                     "lnas": [{"id": afe, "value": {"clamp": 0, "integrator_disable": 0, "gain": 2}}for afe in range(5)]}
                 }
                 } for i in endpoints]}

    print(json.dumps(details, sort_keys=True, indent=4))
    with open(f'np04_daphne_{dev}_cosmics_seed.json', "w") as outfile:
        json.dump(details, outfile, indent=4)

# print(details)
# for i in confs.keys():
#     print(i)