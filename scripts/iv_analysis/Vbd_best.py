'''
Best estimation of the breakdwon voltage, by computing the mean values of Good runs

'''


import click, json
import numpy as np
import pandas as pd
from os import chdir, listdir, path, makedirs, getcwd

import warnings
from datetime import datetime
import sys
import ast


def is_date_valid(file_name):
    match = re.search(r"([A-Za-z]{3}-\d{2}-\d{4})", file_name)
    if match:
        file_date = datetime.strptime(match.group(1), "%b-%d-%Y")
        return file_date >= datetime.strptime("Apr-19-2024", "%b-%d-%Y")
    return False


def check_header(file):
    header_output_file = 'IP\tFile_name\tAPA\tAFE\tConfig_CH\tDAQ_CH\tSIPM_type\tRun\tEndpoint_timestamp\tStart_time\tEnd_time\tBias_data_quality\tBias_min_I\tBias_max_I\tVbd_bias(DAC)\tVbd_bias(V)\tVbd_bias_error(V)\tBias_conversion_slope\tBias_conversion_intercept\tTrim_data_quality\tTrim_min_I\tTrim_max_I\tFit_status\tPoly_Vbd_trim(DAC)\tPoly_Vbd_trim_error(DAC)\tPulse_Vbd_trim(DAC)\tPulse_Vbd_trim_error(DAC)\tVbd(V)\tVbd_error(V)\n'
    with open(file, 'r') as ifile:
        if  ifile.readline() == header_output_file:
            return True
        else:
            return False


def read_data(input_dir, good_runs, input_filename):
    df = pd.DataFrame()
    for run_folder in good_runs:
        chdir(f'{input_dir}/{run_folder}')
        ENDPOINT_FOLDERS = [item for item in sorted(listdir()) if path.isdir(item) and ('ip10.73.137.' in item)]
        for endpoint_folder in ENDPOINT_FOLDERS:
            chdir(f'{input_dir}/{str(run_folder)}/{str(endpoint_folder)}')     
            txt_files = [stringa for stringa in listdir() if stringa.endswith(input_filename)] 
            if len(txt_files) == 1:
                txt_file = txt_files[0]
                if check_header(txt_file):
                    df = pd.concat([df,pd.read_csv(txt_file, sep='\t')], ignore_index=True)
                else:
                    sys.exit(f'{str(endpoint_folder)}/{txt_file} has different output header')                
    df['Endpoint_time'] = pd.to_datetime(df['Endpoint_timestamp'], format='%b-%d-%Y_%H%M')
    #df['ENDPOINT'] = df['IP'].apply(lambda x: x.split('.')[-1])
    return df

def daq_channel_conversion(ch_config):
    afe = int(ch_config//8)
    return 10*(afe) + (ch_config - afe*8)


@click.command()
@click.option("--good_runs", 
              default= ['May-09-2024-run00','May-17-2024_run00','May-28-2024_run00','Jun-18-2024-run00'], # 17May E112C12D14 missing , 18Jun all CH
              help="Good runs, used to make the comparison")
@click.option("--input_dir", 
              default= getcwd() + '/../../data/iv_analysis',
              help="Folder with all run results  (default = 'PDS/data/iv_analysis' ") 
@click.option("--input_filename", 
              default= 'output.txt',
              help="Name of the file you want to read, containing Vbd info (default = 'XX.XX.XXX.XXX_output.txt' ") 
@click.option("--output_path", 
              default= None,
              help="Folder path where data are saved (default: equal to input_dir)")
@click.option("--output_dir_name", 
              default= None,
              help="Name of the folder, to identify this data analysis ")



def main(good_runs, input_dir, input_filename, output_path, output_dir_name):
    good_runs = ast.literal_eval(good_runs)
    if output_path is None:
        output_path = input_dir
    if output_dir_name is None:
        sys.exit('Error: you must specify the name of this analysis!') 

    dir = f'{output_path}/{output_dir_name}'
    if not path.exists(dir):
        makedirs(dir)

    
    df_RUNS = read_data(input_dir, good_runs, input_filename)

    
    for ip in df_RUNS['IP'].unique().tolist():
        print(f'\n\n --- ENDPOINT {ip} --- \n')
        df_ip = df_RUNS[df_RUNS['IP'] == ip]
        apa = df_ip['APA'].unique().tolist()[0] 

        dir_ip = f'{dir}/apa{apa}_ip{ip}'
        if not path.exists(dir_ip):
            makedirs(dir_ip)

        text_file = open(f'{dir_ip}/{ip}_output.txt', 'w') # Fit info
        text_file.write(f'IP\tAPA\tAFE\tConfig_CH\tDAQ_CH\tSIPM_type\tRuns\tBias_conversion_slope\tBias_conversion_intercept\tVbd(V)\tVbd_error(V)\n')
        
        for ch in df_ip['Config_CH'].unique().tolist():
            df_ch = df_ip[df_ip['Config_CH'] == ch]
            afe = df_ch['AFE'].unique().tolist()[0] 
            sipm = df_ch['SIPM_type'].unique().tolist()[0] 
            mean_bias_conversion_slope = df_ch['Bias_conversion_slope'].mean()
            mean_bias_conversion_intercept = df_ch['Bias_conversion_intercept'].mean()
            mean_Vbd = df_ch['Vbd(V)'].mean()
            std_Vbd = df_ch['Vbd(V)'].std()
            print(f'Config_CH {ch} --> Vbd_mean = {mean_Vbd:.3f} +/- {std_Vbd:.3f} V \n')

            text_file.write(f"{ip}\t{apa}\t{afe}\t{ch}\t{daq_channel_conversion(ch)}\t{sipm}\t[{', '.join(good_runs)}]\t{mean_bias_conversion_slope:.5f}\t{mean_bias_conversion_intercept:.5f}\t{mean_Vbd:.4f}\t{std_Vbd:.4f}\n")
    
        text_file.close()
        
    


######################################################################################

if __name__ == "__main__":
    main()
