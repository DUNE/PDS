import re
from datetime import datetime, timedelta
import numpy as np
import click
from os import chdir, listdir
from os.path import isdir
import pandas as pd
from matplotlib import pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from Vbd_plot_utils import *



def CH_VBD_VS_RUN_plot(ax,df,afe):
    ax.set_xlabel('Run time')
    ax.set_ylabel('Vbd (V)') 
    i = 0 
    for config_ch in df['Config_CH'].unique():
        df_ch = df.loc[df['Config_CH'] == config_ch].copy()
        df_ch.loc[:, 'Endpoint_time_shift'] = df_ch['Endpoint_time'] + pd.to_timedelta(4*i, unit='h')
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
        df_afe.loc[:, 'Endpoint_time_shift'] = df_afe['Endpoint_time'] + pd.to_timedelta(4*afe, unit='h')
        ax.errorbar(df_afe['Endpoint_time_shift'], df_afe['mean'], yerr=df_afe['std'] , marker='o', markersize=3.5, capsize=2,linewidth=1 , elinewidth=0.6, color=color_list[afe] , label=f'AFE {afe:.0f}')
    ax.legend(fontsize=7)
    ax.tick_params(axis='x', rotation=45, which='both', labelsize=5)
    ax.tick_params(axis='y', labelsize=8)
    




@click.command()
@click.option("--plot_type", default='ALL') #Vbd_Run
@click.option("--input_dir", default='/afs/cern.ch/user/a/anbalbon/IV_curve/PDS/data/iv_analysis')
@click.option("--output_dir", default='/afs/cern.ch/user/a/anbalbon/IV_curve/PDS/data/iv_analysis')
def main(plot_type, input_dir, output_dir):

    DATA_df = read_data(input_dir)  
    print('\nALL DATA READ\n')  

    
    if (plot_type.upper() == 'CH_VBD_VS_RUN') or (plot_type.upper() == 'ALL'):
        print('Plot of Vbd as a function of run time, for each channel')
        pdf_CH_VBD_VS_RUN = PdfPages(f'{output_dir}/CH_VBD_VS_RUN_plots.pdf') 
        
        for ip in ['10.73.137.104', '10.73.137.105', '10.73.137.107', '10.73.137.109', '10.73.137.111', '10.73.137.112', '10.73.137.113']:
            DATA_df = DATA_df.dropna(subset=['Vbd(V)'])
            df_ip = DATA_df.loc[DATA_df['IP'] == ip]
            if len(df_ip) > 0 :
                AFE_list = df_ip['AFE'].unique()
                '''
                num_plots = len(AFE_list)
                if num_plots == 1:
                    fig, axs = plt.subplots(1, 1, figsize=(10, 8))
                    axs = [axs]
                elif num_plots == 2:
                    fig, axs = plt.subplots(2, 1, figsize=(10, 8))
                elif num_plots == 3:
                    fig, axs = plt.subplots(2, 2, figsize=(10, 8))
                    fig.delaxes(axs[1, 1])
                elif num_plots == 4:
                    fig, axs = plt.subplots(2, 2, figsize=(10, 8))
                elif num_plots == 5:
                    fig, axs = plt.subplots(3, 2, figsize=(10, 8))
                    fig.delaxes(axs[2, 1]) 
                else:
                    raise ValueError('AFE list dimension problem')
                '''
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
        pdf_AFE_VBD_VS_RUN = PdfPages(f'{output_dir}/AFE_VBD_VS_RUN_plots.pdf') 
        DATA_df = DATA_df.dropna(subset=['Vbd(V)'])
        df_grouped = DATA_df.groupby(['IP', 'APA', 'SIPM_type', 'AFE', 'Run', 'Endpoint_time'])['Vbd(V)'].agg(['mean', 'std']).reset_index()

        for ip in map.keys():
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

            
        

if __name__ == "__main__":
    main()