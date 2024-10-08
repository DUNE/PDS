import re
from datetime import datetime, timedelta
import numpy as np
import click
from os import chdir, listdir
from os.path import isdir
import pandas as pd
from matplotlib import pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import sys


#Original map
original_map  = {
    '10.73.137.104': {'apa': 1, 'fbk': [0, 1, 2, 3, 4, 5, 6, 7], 'hpk': [8, 9, 10, 11, 12, 13, 14, 15]},
    '10.73.137.105': {'apa': 1, 'fbk': [0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 13, 15], 'hpk': [17, 19, 20, 22]},
    '10.73.137.107': {'apa': 1, 'fbk': [0, 2, 5, 7], 'hpk': [8, 10, 13, 15]},
    '10.73.137.109': {'apa': 2, 'fbk': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15], 'hpk': [16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39]},
    '10.73.137.111': {'apa': 3, 'fbk': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23], 'hpk': [24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39]},
    '10.73.137.112': {'apa': 4, 'fbk': [], 'hpk': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 34, 37, 39]},
    '10.73.137.113': {'apa': 4, 'fbk': [0, 2, 5, 7], 'hpk': []},
}



# New map from 24/09/2024
map_mod_20240924= {
    '10.73.137.104': {'apa': 1, 'fbk': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23], 'hpk': [24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39]},
    '10.73.137.109': {'apa': 2, 'fbk': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15], 'hpk': [16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39]},
    '10.73.137.111': {'apa': 3, 'fbk': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23], 'hpk': [24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39]},
    '10.73.137.112': {'apa': 4, 'fbk': [], 'hpk': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 34, 37, 39]},
    '10.73.137.113': {'apa': 4, 'fbk': [0, 2, 5, 7], 'hpk': []},
}

color_list = ['red','blue','green','purple','orange','grey','aqua','violet']
color_list_dark = ['darkred','darkblue','darkgreen','indigo','darkorange','darkgrey','deepskyblue','darkviolet']

def daq_channel_conversion(ch_config):
    ch_config = int(ch_config)
    afe = int(int(ch_config)//8)
    return 10*(afe) + (ch_config - afe*8)


def is_date_valid(file_name):
    match = re.search(r"([A-Za-z]{3}-\d{2}-\d{4})", file_name)
    if match:
        file_date = datetime.strptime(match.group(1), "%b-%d-%Y")
        return file_date >= datetime.strptime("Apr-19-2024", "%b-%d-%Y")
    return False


def check_header(file):
    header_output_file_1 = 'IP\tFile_name\tAPA\tAFE\tConfig_CH\tDAQ_CH\tSIPM_type\tRun\tEndpoint_timestamp\tStart_time\tEnd_time\tBias_data_quality\tBias_min_I\tBias_max_I\tVbd_bias(DAC)\tVbd_bias(V)\tVbd_bias_error(V)\tBias_conversion_slope\tBias_conversion_intercept\tTrim_data_quality\tTrim_min_I\tTrim_max_I\tFit_status\tPoly_Vbd_trim(DAC)\tPoly_Vbd_trim_error(DAC)\tPulse_Vbd_trim(DAC)\tPulse_Vbd_trim_error(DAC)\tVbd(V)\tVbd_error(V)\n'
    header_output_file_2 = 'IP\tAPA\tAFE\tConfig_CH\tDAQ_CH\tSIPM_type\tRun\tBias_conversion_slope\tBias_conversion_intercept\tVbd(V)\tVbd_error(V)\n'
    with open(file, 'r') as ifile:
        first_line = ifile.readline()
        if  (first_line == header_output_file_1) or (first_line == header_output_file_2):
            return True
        else:
            return False

def read_data(input_dir, run='ALL'):
    chdir(input_dir)
    RUN_FOLDERS = [file for file in sorted(listdir()) if isdir(file)] #if is_date_valid(file)
    if run != 'ALL':
        RUN_FOLDERS = [file for file in RUN_FOLDERS if file == run]
    
    df = pd.DataFrame()
    for run_folder in RUN_FOLDERS:
        chdir(f'{input_dir}/{str(run_folder)}')
        ENDPOINT_FOLDERS = [item for item in sorted(listdir()) if isdir(item)]
        for endpoint_folder in ENDPOINT_FOLDERS:
            chdir(f'{input_dir}/{str(run_folder)}/{str(endpoint_folder)}')     
            txt_files = [stringa for stringa in listdir() if stringa.endswith("_output.txt")] 
            if len(txt_files) == 1:
                txt_file = txt_files[0]
                if check_header(txt_file):
                    new_df = pd.read_csv(txt_file, sep='\t')
                    new_df['RunFolder'] = run_folder
                    df = pd.concat([df,new_df], ignore_index=True)
                else:
                    print(f'{str(endpoint_folder)}/{txt_file} has different output header')
                    
    return df



def full_map_dataframe(df,map,run_data=''):
    for ip, value in map.items():
        df_ip = df.loc[df['IP'] == ip]
        for ch in value['fbk']+value['hpk']:
            if ch not in df_ip['Config_CH'].values:
                df = pd.concat([df, pd.DataFrame([{'IP':ip , 'AFE':ch//8 , 'Config_CH':ch , 'DAQ_CH':daq_channel_conversion(ch) , 'Run':run_data , 'Vbd(V)':0 , 'Vbd_error(V)':0}])], ignore_index=True)

    df['Stringa_DAQch'] = 'IP' + df['IP'].str[-3:] + '_CH' + df['DAQ_CH'].astype(int).astype(str).str.zfill(2)
    df['Stringa_CONFIGch'] = 'IP' + df['IP'].str[-3:] + '_CH' + df['Config_CH'].astype(int).astype(str).str.zfill(2)
    df = df.sort_values(by='Stringa_DAQch')
    
    if len(df) != 160:
        print('ERROR')
        return 0
    else:
        return df

def custom_mean(x):
    if x.isnull().any():
        return 0
    else:
        return x.mean()

def custom_std(x):
    if x.isnull().any():
        return 0
    else:
        return x.std()
    
    
    
def endpoint_list_data(folder_name):
    new_conf_data = datetime(2024, 9, 24)
    if 'run' in folder_name:
        string_data = datetime.strptime(folder_name.split('-run')[0], '%b-%d-%Y')
    elif 'Vbd_best_' in folder_name:
        string_data = datetime.strptime(folder_name.split('Vbd_best_')[-1], '%Y%m%d')
    else:
        sys.exit('Error: you must specify the name of this analysis!') 
        
    if string_data >= new_conf_data:
        endpoint_list = ['104','109', '111', '112', '113']
        map_to_use = map_mod_20240924
    else:
        endpoint_list = ['104', '105', '107', '109', '111', '112', '113']
        map_to_use = original_map
    return map_to_use

        