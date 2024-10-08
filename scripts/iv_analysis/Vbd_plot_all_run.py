import re
from datetime import datetime, timedelta
import numpy as np
import click
from os import chdir, listdir, getcwd
from os.path import isdir
import pandas as pd
from matplotlib import pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import ast
from Vbd_plot_utils import *
import json


def CH_VBD_VS_RUN_plot(ax,df,afe):
    ax.set_xlabel('Run time')
    ax.set_ylabel('Vbd (V)') 
    i = 0 
    for config_ch in df['Config_CH'].unique():
        df_ch = df.loc[df['Config_CH'] == config_ch].copy()
        df_ch.loc[:, 'Endpoint_time_shift'] = df_ch['Endpoint_time'] + pd.to_timedelta(10*i, unit='h')
        df_ch=df_ch.sort_values(by='Endpoint_time_shift')
        ax.errorbar(df_ch['Endpoint_time_shift'], df_ch['Vbd(V)'], yerr=df_ch['Vbd_error(V)'] , marker='o', markersize=3.5, capsize=2,linewidth=1 , elinewidth=0.6, color=color_list[int(config_ch)-8*(int(config_ch)//8)] , label=f'Config_CH={config_ch} DAQ_CH={daq_channel_conversion(config_ch):.0f}')
        i+=1
    ax.legend(fontsize=3)
    ax.tick_params(axis='x', rotation=45, which='both', labelsize=5)
    #ax.tick_params(axis='x', labelsize=5)
    ax.tick_params(axis='y', labelsize=8)
    
    

def AFE_VBD_VS_RUN_plot(ax,df,sipm):
    ax.set_xlabel('Run time')
    ax.set_ylabel('Mean AFE Vbd (V)') 
    color_list = ['red','blue','green','purple','orange']
    for afe in df['AFE'].unique():
        df_afe = df.loc[df['AFE'] == afe].copy()
        df_afe.loc[:, 'Endpoint_time_shift'] = df_afe['Endpoint_time'] + pd.to_timedelta(10*afe, unit='h')
        df_afe=df_afe.sort_values(by='Endpoint_time_shift')
        ax.errorbar(df_afe['Endpoint_time_shift'], df_afe['mean'], yerr=df_afe['std'] , marker='o', markersize=3.5, capsize=2,linewidth=1 , elinewidth=0.6, color=color_list[afe] , label=f'AFE {afe:.0f}')
    ax.legend(fontsize=7)
    ax.tick_params(axis='x', rotation=45, which='both', labelsize=5)
    ax.tick_params(axis='y', labelsize=8)
    




@click.command()
@click.option("--plot_type", 
              default='ALL',
              type=click.Choice(['CH_VBD_VS_RUN', 'AFE_VBD_VS_RUN', 'MEAN_CH_VDB', 'ALL'], case_sensitive=False),
              help="Type of plot you want (options: CH_VBD_VS_RUN, AFE_VBD_VS_RUN, MEAN_CH_VDB, 'ALL', default: 'ALL')")
@click.option("--input_dir", 
              default= getcwd() + '/../../data/iv_analysis',
              help="Path directory where all iv analysis results are saved, of all runs (default: 'PDS/data/iv_analysis'")
@click.option("--output_dir", 
              default= getcwd() + '/../../data/iv_analysis',
              help="Path directory where save plots (default: 'PDS/data/iv_analysis')")
@click.option("--run_exluded", 
              default= None ,
              help="Run to exlude from the analysis, by default we consider all data but for example you can remove ['Jun-07-2024-run00','Jul-02-2024-run00', 'Jul-31-2024-run00']")



def main(plot_type, input_dir, output_dir,run_exluded):

    if run_exluded is None:
        run_exluded = []
    else:
        run_exluded = ast.literal_eval(run_exluded)
    
    DATA_df = read_data(input_dir)  
    DATA_df['Endpoint_time'] = pd.to_datetime(DATA_df['Endpoint_timestamp'], format='%b-%d-%Y_%H%M')
    DATA_df = DATA_df[DATA_df['RunFolder'].apply(is_date_valid)]
    DATA_df = DATA_df[~DATA_df['RunFolder'].isin(run_exluded)]
    print('\nALL DATA READ\n')  
    
    
    dates_cleaned = [pd.to_datetime(date.split('-run')[0], format='%b-%d-%Y') for date in DATA_df['RunFolder'].unique()]
    dates_after_ref = [date for date in dates_cleaned if date >= pd.to_datetime('2024-09-24')]
    if len(dates_after_ref) > 0:
        endpoint_list = ['10.73.137.104', '10.73.137.109', '10.73.137.111', '10.73.137.112', '10.73.137.113']
        
        with open('/afs/cern.ch/user/a/anbalbon/IV_curve/PDS/maps/map_changing_20240924/correlation_map_end104.json', 'r') as file:
            correlation_map = json.load(file)

    
        for new_ch, value in correlation_map.items():
            old_ip = f"10.73.137.{value['endpoint']}"
            old_ch = int(value['channel'])
            

            DATA_df.loc[
                (DATA_df['IP'] == old_ip) & 
                (DATA_df['Config_CH'] == old_ch) & 
                (DATA_df['Endpoint_time'] < pd.to_datetime('2024-09-24')), 
                ['IP', 'Config_CH', 'DAQ_CH', 'AFE']
            ] = [
                '10.73.137.104', 
                new_ch, 
                daq_channel_conversion(new_ch), 
                int(int(new_ch) // 8)
            ] 
        
    else:
        endpoint_list = ['10.73.137.104', '10.73.137.105', '10.73.137.107', '10.73.137.109', '10.73.137.111', '10.73.137.112', '10.73.137.113']

    DATA_df['Config_CH'] = DATA_df['Config_CH'].astype(int)
    DATA_df['DAQ_CH'] = DATA_df['DAQ_CH'].astype(int)

    if (plot_type.upper() == 'CH_VBD_VS_RUN') or (plot_type.upper() == 'ALL'):
        print('Plot of Vbd as a function of run time, for each channel')
        if len(run_exluded)==0:
            pdf_CH_VBD_VS_RUN = PdfPages(f'{output_dir}/CH_VBD_VS_RUN_complete_plots.pdf') 
        else:
            pdf_CH_VBD_VS_RUN = PdfPages(f'{output_dir}/CH_VBD_VS_RUN_good_plots.pdf') 
        
        for ip in endpoint_list:
            DATA_df = DATA_df.dropna(subset=['Vbd(V)'])
            df_ip = DATA_df.loc[DATA_df['IP'] == ip]
            if len(df_ip) > 0 :
                fig, axs = plt.subplots(3, 2, figsize=(10, 8))
                fig.delaxes(axs[2, 1]) 
                axs = np.ravel(axs)
                fig.suptitle(f'ENDPOINT:{ip[-3:]}')
                for afe in range(5):
                    df_ip_afe = df_ip.loc[df_ip['AFE'] == afe]
                    axs[afe].set_title(f'AFE {afe:.0f}')
                    if len(df_ip_afe)>0:
                        CH_VBD_VS_RUN_plot(axs[afe],df_ip_afe,afe)
                    else:
                        axs[afe].set_xticks([])
                        axs[afe].set_yticks([])
                plt.tight_layout()
                pdf_CH_VBD_VS_RUN.savefig(fig)
                plt.close(fig)
        pdf_CH_VBD_VS_RUN.close()
            
       

    if (plot_type.upper() == 'AFE_VBD_VS_RUN') or (plot_type.upper() == 'ALL'):
        print('Plot of mean Vbd per afe as a function of run time, for each afe')
        if len(run_exluded)==0:
            pdf_AFE_VBD_VS_RUN = PdfPages(f'{output_dir}/AFE_VBD_VS_RUN_complete_plots.pdf') 
        else:
            pdf_AFE_VBD_VS_RUN = PdfPages(f'{output_dir}/AFE_VBD_VS_RUN_good_plots.pdf') 
        
        DATA_df = DATA_df.dropna(subset=['Vbd(V)'])
        df_grouped = DATA_df.groupby(['IP', 'APA', 'SIPM_type', 'AFE', 'Run', 'Endpoint_time'])['Vbd(V)'].agg(['mean', 'std']).reset_index()

        for ip in endpoint_list:
            df_ip = df_grouped.loc[df_grouped['IP'] == ip]
            if len(df_ip) > 0 :
                fig, axs = plt.subplots(2, 1, figsize=(10, 8))
                fig.suptitle(f'ENDPOINT:{ip[-3:]}')
                axs = np.ravel(axs)
                i=0
                for sipm in ['HPK','FBK']:
                    df_ip_sipm = df_ip.loc[df_ip['SIPM_type'] == sipm]
                    axs[i].set_title(f'SiPM: {sipm} ')
                    if len(df_ip_sipm)>0:
                        AFE_VBD_VS_RUN_plot(axs[i],df_ip_sipm,sipm)
                    else:
                        axs[i].set_xticks([])
                        axs[i].set_yticks([])
                    i+=1
                plt.tight_layout()
                pdf_AFE_VBD_VS_RUN.savefig(fig)
                plt.close(fig)
                
        pdf_AFE_VBD_VS_RUN.close()

        #pd.set_option('display.max_rows', None)
        #print(df_grouped)

    '''
    # TO BE FINISHED!
    if (plot_type.upper() == 'MEAN_CH_VDB') or (plot_type.upper() == 'ALL'): 
        print('Plot of mean Vbd per CH in time')
        min_data = DATA_df['Endpoint_time'].min()
        max_data = DATA_df['Endpoint_time'].max()

        #df_grouped = DATA_df.groupby(['IP', 'APA', 'SIPM_type', 'AFE', 'Config_CH', 'DAQ_CH'])['Vbd(V)'].agg(['mean', 'std']).reset_index()
        df_grouped = DATA_df.groupby(['IP', 'APA', 'SIPM_type', 'AFE', 'Config_CH', 'DAQ_CH'])['Vbd(V)'].agg([('mean', custom_mean) , ('std', custom_std)]).reset_index()
        df_grouped= full_map_dataframe(df_grouped)
        df_grouped.loc[df_grouped['Vbd(V)'] == 0, ['mean', 'std']] = 0

        pdf_MEAN_CH_VDB = PdfPages(f'{output_dir}/MEAN_CH_VDB_plot.pdf')
        fig, ax = plt.subplots(1, figsize=(16, 7))
        fig.suptitle(f'Mean CH Vbd \n From {min_data} to {max_data}')
        for i, ip in enumerate(df_grouped['IP'].unique()):
            df_ip = df_grouped.loc[df_grouped['IP'] == ip]
            ax.errorbar(df_ip['Stringa_DAQch'], df_ip['mean'], yerr=df_ip['std'] , marker='o', markersize=1, capsize=2,linewidth=0 , elinewidth=0.6, color=color_list[i] , label=f'Endpoint: {ip}')

        ax.set_xlabel('DAQ channel')
        ax.set_ylabel('Vbd (V)') 
        plt.xticks(rotation=90, fontsize=5)
        plt.grid(linewidth=0.3)
        plt.legend()
        plt.tight_layout()
        pdf_MEAN_CH_VDB.savefig(fig)
        plt.close(fig)
        
        pdf_MEAN_CH_VDB.close()

     '''       
        

if __name__ == "__main__":
    main()