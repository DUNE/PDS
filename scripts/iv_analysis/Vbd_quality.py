'''

Comparison between Vbd of a given run and previous (good) runs

 -- Remember to update the list of good runs manually!!! --

'''


import click, json
import numpy as np
import pandas as pd
from os import chdir, listdir, path, makedirs, getcwd
import ast
from datetime import datetime
import sys
import matplotlib.pyplot as plt

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

def read_data(input_dir, good_runs):
    df = pd.DataFrame()
    for run_folder in good_runs:
        chdir(f'{input_dir}/{run_folder}')
        ENDPOINT_FOLDERS = [item for item in sorted(listdir()) if path.isdir(item) and ('ip10.73.137.' in item)]
        for endpoint_folder in ENDPOINT_FOLDERS:
            chdir(f'{input_dir}/{str(run_folder)}/{str(endpoint_folder)}')     
            txt_files = [stringa for stringa in listdir() if stringa.endswith("_output.txt")] 
            if len(txt_files) == 1:
                txt_file = txt_files[0]
                if check_header(txt_file):
                    df = pd.concat([df,pd.read_csv(txt_file, sep='\t')], ignore_index=True)
                else:
                    print(f'{str(endpoint_folder)}/{txt_file} has different output header')               
    df['Endpoint_time'] = pd.to_datetime(df['Endpoint_timestamp'], format='%b-%d-%Y_%H%M')
    return df

def most_recent_run(input_dir):
    all_runs = [d for d in listdir(input_dir) if (path.isdir(path.join(input_dir, d))) and ('run' in d)]
    recent_date = max(all_runs, key=lambda date: datetime.strptime(date.split('_')[0] if '_' in date else date.split('-run')[0], '%b-%d-%Y')).split('_')[0] if '_' in max(all_runs, key=lambda date: datetime.strptime(date.split('_')[0] if '_' in date else date.split('-run')[0], '%b-%d-%Y')) else max(all_runs, key=lambda date: datetime.strptime(date.split('_')[0] if '_' in date else date.split('-run')[0], '%b-%d-%Y')).split('-run')[0]
    matching_folders = [folder for folder in listdir(input_dir) if path.isdir(path.join(input_dir, folder)) and recent_date in folder]

    if len(matching_folders) == 0:
        sys.exit('Error: unable to find the most recent run!') 
    elif len(matching_folders) == 1:
        return matching_folders[0]
    else:
        print('Attention, there are more than one run with the same date (associeted to the most recent run):')
        print(matching_folders)
        selected = input('Which one do you want to use?\t')
        return selected
    
@click.command()
@click.option("--run", 
              default= None,
              help="Run to analyze (default: the last run")
@click.option("--good_runs", 
              default= ['Apr-22-2024-run01','Apr-23-2024-run00','Apr-27-2024-run00','May-02-2024-run00','May-09-2024-run00','May-17-2024-run00','May-28-2024-run00','Jun-18-2024-run00','Jul-29-2024-run00'], # 17May E112C12D14 missing , 18Jun all CH
              help="Good runs, used to make the comparison")
@click.option("--input_dir", 
              default= getcwd() + '/../../data/iv_analysis',
              help="Path directory where all iv analysis results are saved, of all runs (default: 'PDS/data/iv_analysis'")
@click.option("--output_dir", 
              default= getcwd() + '/../../data/iv_analysis',
              help="Path directory where save plots (default: 'PDS/data/iv_analysis')")
@click.option("--threshold", 
              default= 0.25,
              help="Theshold (in Volts) for the difference between the mean Vbd value and the current one")


def main(run, good_runs, input_dir, output_dir, threshold):
    if run == None :
        run = most_recent_run(input_dir)

    good_runs = ast.literal_eval(good_runs)
    df_RUNS = read_data(input_dir, good_runs)
    
    chdir(f'{input_dir}/{run}')
    ENDPOINT_FOLDERS = [item for item in sorted(listdir()) if (path.isdir(item)) and ('ip10.73.137.' in item)]
    diff_list = []
    for endpoint_folder in ENDPOINT_FOLDERS:
        print(f'\n\n ---{endpoint_folder} ---\n')
        ip = endpoint_folder.split('ip')[-1]
        apa = endpoint_folder.split('apa')[1][0]

        chdir(f'{input_dir}/{run}/{endpoint_folder}')
        txt_files = [stringa for stringa in listdir() if stringa.endswith("_output.txt")] 
        if len(txt_files) == 1:
            txt_file = txt_files[0]
            if check_header(txt_file):
                df_run = pd.read_csv(txt_file, delimiter='\t')
                for index, row in df_run.iterrows():
                    ch = row['Config_CH']
                    Vbd_now = df_run[df_run['Config_CH'] == ch]['Vbd(V)'].values[0]
                    Vbd_mean =  df_RUNS[(df_RUNS['IP'] == ip) & (df_RUNS['Config_CH'] == ch)]['Vbd(V)'].mean()
                    Vbd_old = df_RUNS[(df_RUNS['IP'] == ip) & (df_RUNS['Config_CH'] == ch)]['Vbd(V)'].to_numpy()

                    if np.isnan(Vbd_old).all():
                        print(f'Config_CH {ch} had always NaN Vbd values', end=' ')
                        if np.isnan(Vbd_now):
                            print(f'and it is still NaN \t-> OK (dead/disconnected ch)')
                        else:
                            print(f", but now its value is {Vbd_now} \t-> CHECK !!!!! ")
                    elif np.isnan(Vbd_old).any():
                        print(f"Config_CH {ch} had some NaN Vbd values: {Vbd_old} and now its value is {Vbd_now} \t-> CHECK !!!!!")
                    else:
                        print(f'Config_CH {ch} had always NO NaN Vbd values', end=' ')
                        if np.isnan(Vbd_now):
                            print(f', but now it has a NaN value \t-> CHECK !!!!!')
                        else:
                            print(f"and it is still ({Vbd_now:.3f}V)", end=' ')
                            diff = Vbd_now - Vbd_mean
                            diff_list.append(diff)
                            if abs(diff) > threshold:
                                print(f'\t -> ATTENTION: Diff |{abs(diff):.3f}| > {threshold} V')
                            else:
                                print('\t -> OK')
                      
            else:
                sys.exit(f'{str(endpoint_folder)}/{txt_file} has different output header') 
        
    plt.hist(diff_list, bins=50, edgecolor='black')
    plt.title(f'Run comparison: {run}')
    
    plt.xlabel(r'$V_{bd}-V_{mean}$ (V)')
    plt.ylabel('Counts')
    plt.savefig(f'{input_dir}/{run}/comparison_hist.pdf')
    plt.close()

    print()

######################################################################################

if __name__ == "__main__":
    main()
