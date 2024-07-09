import re
from datetime import datetime, timedelta
import numpy as np
import click
from os import chdir, listdir, path, getcwd
from os.path import isdir
import pandas as pd
from matplotlib import pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from Vbd_plot_utils import *


def check_header_2(file):
    header_output_file_1 = 'IP\tFile_name\tAPA\tAFE\tConfig_CH\tDAQ_CH\tSIPM_type\tRun\tEndpoint_timestamp\tStart_time\tEnd_time\tBias_data_quality\tBias_min_I\tBias_max_I\tVbd_bias(DAC)\tVbd_bias(V)\tVbd_bias_error(V)\tBias_conversion_slope\tBias_conversion_intercept\tTrim_data_quality\tTrim_min_I\tTrim_max_I\tFit_status\tPoly_Vbd_trim(DAC)\tPoly_Vbd_trim_error(DAC)\tPulse_Vbd_trim(DAC)\tPulse_Vbd_trim_error(DAC)\tVbd(V)\tVbd_error(V)\n'
    header_output_file_2 = 'IP\tAPA\tAFE\tConfig_CH\tDAQ_CH\tSIPM_type\tRun\tBias_conversion_slope\tBias_conversion_intercept\tVbd(V)\tVbd_error(V)\n'
    with open(file, 'r') as ifile:
        first_line = ifile.readline()
        if  (first_line == header_output_file_1) or (first_line == header_output_file_2):
            return True
        else:
            return False
            

def read_data_2(input_dir, run='ALL'):
    chdir(input_dir)
    RUN_FOLDERS = [file for file in sorted(listdir())]
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
                if check_header_2(txt_file):
                    df = pd.concat([df,pd.read_csv(txt_file, sep='\t')], ignore_index=True)
                else:
                    print(f'{str(endpoint_folder)}/{txt_file} has different output header')
    return df


def VB_HIST_X_RUN(ax,df,sipm):
    ax.set_title(f'SiPM: {sipm}')
    ax.set_xlabel('Vbd (V)')
    ax.set_ylabel('Counts') 
    
    color_list = ['red','blue','green','purple','orange','grey','aqua','violet']
    for j, ip in enumerate(df['IP'].unique()):
        df_ip = df.loc[df['IP'] == ip]
        ax.hist(df_ip['Vbd(V)'], bins=7, alpha=0.3, color=color_list[j], edgecolor=color_list[j], linewidth=1.5, label=f'Endpoint: {ip}')
    ax.legend(fontsize=8)


@click.command()
@click.option("--plot_type", 
              default='ALL',
              type=click.Choice(['CH_VBD_X_RUN', 'VB_HIST_X_RUN', 'ALL'], case_sensitive=False),
              help="Type of plot you want (options: CH_VBD_X_RUN, VB_HIST_X_RUN, 'ALL', default: 'ALL')")
@click.option("--input_dir", 
              default= getcwd() + '/../../data/iv_analysis',
              help="Path directory where all iv analysis results are saved, of all runs (default: 'PDS/data/iv_analysis'")
@click.option("--output_dir", 
              default= getcwd() + '/../../data/iv_analysis',
              help="Path directory where save plots (default: 'PDS/data/iv_analysis')")
@click.option("--run", 
              default='ALL',
              help="Run you want to study, such as May-17-2024_run00 (default: 'ALL'") 




def main(plot_type, input_dir, output_dir, run):
    DATA_df = read_data_2(input_dir,run)  
    print('\nALL DATA READ\n')  
    print(DATA_df)

    if (plot_type.upper() == 'CH_VBD_X_RUN') or (plot_type.upper() == 'ALL'):
        print('Plot of Vbd as a function of channel number, for a given run')
        DATA_df = DATA_df.dropna(subset=['Vbd(V)'])
        pdf_CH_VBD_all = PdfPages(f'{output_dir}/CH_VBD_vs_RUN_all.pdf')
        
        if path.exists(f'{output_dir}/{run}'):
            pdf_CH_VBD_single = PdfPages(f'{output_dir}/{run}/CH_VBD_plot.pdf')
        else:
            pdf_CH_VBD_single = PdfPages(f'{output_dir}/{run}_CH_VBD_plot.pdf')

        DATA_df_completed = full_map_dataframe(DATA_df, run)    

        fig, ax = plt.subplots(1, figsize=(16, 7))
        fig.suptitle(f'Channel Vbd \n RUN: {run}')
        i=0
        for ip in DATA_df_completed['IP'].unique():
            df_ip = DATA_df_completed.loc[DATA_df_completed['IP'] == ip]
            ax.errorbar(df_ip['Stringa_DAQch'], df_ip['Vbd(V)'], yerr=df_ip['Vbd_error(V)'] , marker='o', markersize=3.5, capsize=2,linewidth=0 , elinewidth=0.6, color=color_list[i] , label=f'Endpoint: {ip}')
            i+=1
        ax.set_xlabel('DAQ channel')
        ax.set_ylabel('Vbd (V)') 
        plt.xticks(rotation=90, fontsize=5)
        plt.grid(linewidth=0.3)
        plt.legend()
        plt.tight_layout()
        pdf_CH_VBD_single.savefig(fig)
        pdf_CH_VBD_all.savefig(fig)
        plt.close(fig)
        
        pdf_CH_VBD_single.close()
        pdf_CH_VBD_all.close()
    



if __name__ == "__main__":
    main()