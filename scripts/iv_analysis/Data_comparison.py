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
import json
from matplotlib.lines import Line2D
import seaborn as sns



def format_endch(num):
        num_str = str(num)  # Convertire il numero in stringa
        if len(num_str) > 3:  # Inserire il '_' tra la terza e quarta cifra
            return num_str[:3] + '_' + num_str[3:]
        return num_str  # Se la stringa ha meno di 4 cifre, la restituisce senza modifiche
 

   

@click.command()
@click.option("--input_dir", 
              default= getcwd() + '/../../data/iv_analysis',
              help="Folder with all IV curve results (default = '/data/iv_analysis')") 
@click.option("--new_run", 
              default= 'Vbd_best_20241007',
              help="Run with new configuration (default = 'Vbd_best_20241007')") 
@click.option("--old_run", 
              default= 'Vbd_best_20240730',
              help="Run with old configuration (default = 'Vbd_best_20240730')") 
@click.option("--correlation_map_path", 
              default= '/afs/cern.ch/user/a/anbalbon/IV_curve/PDS/maps/map_changing_20240924/correlation_map_end104.json',
              help="Path of the map with old-new channel/endpoint correlation (deault = 'maps/map_changing_20240924/correlation_map_end104.json')") 
@click.option("--ln2t_data_path", 
              default= getcwd() + '/../../data/iv_analysis/Comparison_plots/LN2T_coldbox_data.txt',
              help="Path of the txt file with LN2T Coldbox data  (default = '/afs/cern.ch/user/a/anbalbon/IV_curve/PDS/scripts/iv_analysis/dati.txt')") 
@click.option("--output_dir", 
              default= getcwd() + '/../../data/iv_analysis/Comparison_plots',
              help="Folder with all IV curve results (default = '/data/iv_analysis/comparison_plots')") 

@click.option("--oldnew_diff_hist", 
              default= 'yes',
              help="Do you want to create the histogram with Old - New Vbd difference (yes/no)?") 
@click.option("--oldnew_scatter", 
              default= 'yes',
              help="Do you want to create the scatter plot with Old and New Vbd (yes/no)?") 
@click.option("--oldnew_diff_scatter", 
              default= 'yes',
              help="Do you want to create the scatter plot with Old - New Vbd difference (yes/no)?") 

@click.option("--newln2t_scatter", 
              default= 'yes',
              help="Do you want to create the scatter plot with LN2T and New Vbd (yes/no)?") 
@click.option("--newln2t_diff_scatter", 
              default= 'yes',
              help="Do you want to create the scatter plot with New - Vbd (yes/no)?") 
@click.option("--newln2t_diff_hist", 
              default= 'yes',
              help="Do you want to create the histogram with New - LN2T Vbd difference (yes/no)?")

@click.option("--oldln2t_scatter", 
              default= 'yes',
              help="Do you want to create the scatter plot with LN2T and Old Vbd (yes/no)?") 
@click.option("--oldln2t_diff_scatter", 
              default= 'yes',
              help="Do you want to create the scatter plot with Old - Vbd (yes/no)?") 
@click.option("--oldln2t_diff_hist", 
              default= 'yes',
              help="Do you want to create the histogram with Old - LN2T Vbd difference (yes/no)?")

def main(input_dir, new_run, old_run, correlation_map_path, ln2t_data_path, output_dir, oldnew_diff_hist, oldnew_scatter, oldnew_diff_scatter, newln2t_scatter, newln2t_diff_scatter, newln2t_diff_hist, oldln2t_scatter, oldln2t_diff_scatter, oldln2t_diff_hist):
    
    with open(correlation_map_path, 'r') as file:
        correlation_map = json.load(file) 

    New_df = read_data(input_dir,new_run) 
    Old_df = read_data(input_dir,old_run) 
    

    LN2T_df = pd.read_csv(ln2t_data_path, sep='\s+') #delim_whitespace=True
    LN2T_df['EndCh'] = LN2T_df['EndCh'].apply(format_endch)
    LN2T_df['End'] = LN2T_df['EndCh'].str[:3].astype(int)
    LN2T_df['DAQ_CH'] = LN2T_df['EndCh'].str[-2:].astype(int)
    
   
    New_df.rename(columns={'Vbd(V)': 'New Vbd(V)'}, inplace=True)
    New_df.rename(columns={'Vbd_error(V)': 'New Vbd_error(V)'}, inplace=True)
    New_df['DAQ_CH'] = New_df['DAQ_CH'].astype(int)
    New_df['Config_CH'] = New_df['Config_CH'].astype(int)
    New_df['Stringa_DAQch'] = 'IP' + New_df['IP'].str[-3:] + '_CH' + New_df['DAQ_CH'].astype(int).astype(str).str.zfill(2)
    New_df['End'] = New_df['IP'].str[-3:].astype(int)
    
    Old_df['DAQ_CH'] = Old_df['DAQ_CH'].astype(int)
    Old_df['Config_CH'] = Old_df['Config_CH'].astype(int)
    Old_df['Stringa_DAQch'] = 'IP' + Old_df['IP'].str[-3:] + '_CH' + Old_df['DAQ_CH'].astype(int).astype(str).str.zfill(2)
    Old_df['End'] = Old_df['IP'].str[-3:].astype(int)
    
    New_df['Old Vbd(V)'] = None
    New_df['Old Vbd_error(V)'] = None
    New_df['Diff Old_New'] = None
    New_df['Coldbox_LN2T Vbd(V)'] = None
    New_df['Coldbox_LN2T Vbd_error(V)'] = None
    New_df['Diff New_LN2T'] = None 
    New_df['Diff Old_LN2T'] = None 
    
    
        
    for index, row in New_df.iterrows():
        new_end = row['End']
        new_config_ch = row['Config_CH']
        new_daq_ch = row['DAQ_CH']
        
        new_Vbd = New_df[(New_df['Config_CH'] == new_config_ch) & (New_df['End'] == new_end)].iloc[0]['New Vbd(V)']
         
        if new_end == 104:
            old_config_ch = int(correlation_map[str(new_config_ch)]['channel'])
            old_end = int(correlation_map[str(new_config_ch)]['endpoint'])
            old_daq_ch = daq_channel_conversion(old_config_ch)
                                        
        else:
            old_end = new_end
            old_config_ch = new_config_ch
            old_daq_ch = new_daq_ch
                
        old_Vbd = Old_df[(Old_df['Config_CH'] == old_config_ch) & (Old_df['End'] == old_end)].iloc[0]['Vbd(V)']
        old_Vbd_error = Old_df[(Old_df['Config_CH'] == old_config_ch) & (Old_df['End'] == old_end)].iloc[0]['Vbd_error(V)']
        
        if pd.isna(old_Vbd) or pd.isna(new_Vbd):
            diff_old_new = None
        else:
            diff_old_new = old_Vbd - new_Vbd
        
        New_df.at[index, 'Old Vbd(V)'] = old_Vbd
        New_df.at[index, 'Old Vbd_error(V)'] = old_Vbd_error
        New_df.at[index,'Diff Old_New'] = diff_old_new        
    
        LN2T_Vbd_list = LN2T_df.loc[(LN2T_df['DAQ_CH'] == old_daq_ch) & (LN2T_df['End'] == old_end)]['Coldboard_LN2T'].tolist()
        if len(LN2T_Vbd_list) == 1:
            LN2T_Vbd = LN2T_Vbd_list[0]
            diff_new_LN2T = new_Vbd - LN2T_Vbd
            diff_old_LN2T = old_Vbd - LN2T_Vbd
            New_df.at[index,'Diff New_LN2T'] = diff_new_LN2T 
            New_df.at[index,'Diff Old_LN2T'] = diff_old_LN2T 
        else:
            LN2T_Vbd = None
        New_df.at[index, 'Coldbox_LN2T Vbd(V)'] = LN2T_Vbd

    df = New_df
    df['EndCh'] = (df['Stringa_DAQch'].str.replace('IP', '', regex=False).str.replace('CH', '', regex=False))
    df_104 = df[df['IP'] == '10.73.137.104']
    
    del New_df
    del Old_df
    del LN2T_df
    
    
    ##################################################################################
    ##################################################################################
    
    
    ''' New vs Old data - Endpoint 104 '''
    
    
    # Histogram: Old - New Vbd value (only endpoint 104)
    if oldnew_diff_hist == 'yes':
        plt.hist(df_104['Diff Old_New'], bins=14,color='skyblue', edgecolor='black')
        plt.title("New endpoint 104 \nChannel Vbd difference: New - Old LAr IV results")
        plt.xlabel("Vbd old - new (V)")
        plt.ylabel("Counts")
        plt.savefig(f'{output_dir}/New_vs_Old/oldnew_diff_hist.jpg', dpi=300)
        plt.close()
    
    
    # Scatter plot: Old and New Vbd value (only endpoint 104)
    if oldnew_scatter == 'yes':
        fig, axs = plt.subplots(3, 2, figsize=(10, 8))
        fig.delaxes(axs[2, 1]) 
        axs = np.ravel(axs)
        fig.suptitle(f"New endpoint 104 \nChannel Vbd comparison: New - Old LAr IV results ")    
        for afe in df_104['AFE'].unique():
            df_afe = df_104.loc[df_104['AFE'] == afe]
            axs[afe].set_title(f'AFE {afe:.0f}')
            axs[afe].errorbar(df_afe['DAQ_CH'], df_afe['New Vbd(V)'], yerr=df_afe['New Vbd_error(V)'] , marker='o', markersize=3.5, capsize=2,linewidth=0 , elinewidth=0.6, color='red' , label=f'New')
            axs[afe].errorbar(df_afe['DAQ_CH']+0.1, df_afe['Old Vbd(V)'], yerr=df_afe['Old Vbd_error(V)'] , marker='o', markersize=3.5, capsize=2,linewidth=0 , elinewidth=0.6, color='orange' , label=f'Old')
            axs[afe].set_xlabel('DAQ channel')
            axs[afe].set_ylabel('Vbd (V)') 
            axs[afe].legend(fontsize=7)
            axs[afe].tick_params(axis='x', which='both', labelsize=5)
            axs[afe].tick_params(axis='y', labelsize=8)
            
        plt.tight_layout()
        plt.savefig(f'{output_dir}/New_vs_Old/oldnew_scatter.jpg', dpi=300)
        plt.close(fig)

    # Scatter plot: Old and New Vbd difference (only endpoint 104)
    if oldnew_diff_scatter == 'yes':
        fig, ax = plt.subplots(1, figsize=(16, 7))
        fig.suptitle(f"New endpoint 104 \nChannel Vbd difference: New - Old LAr IV results")
        for afe in df_104['AFE'].unique():
            df_afe = df_104.loc[df_104['AFE'] == afe]
            ax.errorbar(df_afe['DAQ_CH'], df_afe['Diff Old_New'], marker='o', markersize=3.5, capsize=2,linewidth=0 , elinewidth=0.6, color=color_list[afe] , label=f"Afe: {afe} ({df_afe['SIPM_type'].unique()[0]})")
        ax.set_xlabel('DAQ channel')
        ax.set_ylabel('Vbd diff Old-New (V)') 
        plt.xticks(ticks=df['DAQ_CH'])
        plt.grid(linewidth=0.3)
        plt.legend()
        plt.tight_layout()
        plt.savefig(f'{output_dir}/New_vs_Old/oldnew_diff_scatter.jpg', dpi=300)
        plt.close(fig)

    ##################################################################################
    ##################################################################################
    
    
    ''' New vs LN2T data'''
    
    
    # Scatter plot: LN2T and New Vbd value (only endpoint 104)
    if newln2t_scatter == 'yes':    
        fig, axs = plt.subplots(3, 2, figsize=(10, 8))
        fig.delaxes(axs[2, 1]) 
        axs = np.ravel(axs)
        fig.suptitle(f"New endpoint 104 \nChannel Vbd comparison: New LAr IV results -  Coldbox LN2T tests")    
        for afe in df_104['AFE'].unique():
            df_afe = df_104.loc[df_104['AFE'] == afe]
            axs[afe].set_title(f"AFE {afe:.0f} - {df_afe['SIPM_type'].unique()[0]}")
            axs[afe].errorbar(df_afe['DAQ_CH'], df_afe['New Vbd(V)'], yerr=0 , marker='o', markersize=3.5, capsize=2,linewidth=0 , elinewidth=0.6, color='red' , label=f'New LAr')
            axs[afe].errorbar(df_afe['DAQ_CH']+0.1, df_afe['Coldbox_LN2T Vbd(V)'], yerr=0 , marker='o', markersize=3.5, capsize=2,linewidth=0 , elinewidth=0.6, color='orange' , label=f'LN2T')
            axs[afe].set_xlabel('DAQ channel')
            axs[afe].set_ylabel('Vbd (V)') 
            axs[afe].legend(fontsize=7)
            axs[afe].tick_params(axis='x', which='both', labelsize=5)
            axs[afe].tick_params(axis='y', labelsize=8)

        plt.tight_layout()
        plt.savefig(f'{output_dir}/New_vs_LN2T/newln2t_scatter.jpg', dpi=300)
        plt.close(fig)
    
    # Scatter plot: LN2T and New Vbd value (only endpoint 104)
    if newln2t_diff_scatter == 'yes':   
        fig, ax = plt.subplots(1, figsize=(16, 7))
        fig.suptitle(f"New endpoint 104 \nChannel Vbd difference: New LAr IV results -  Coldbox LN2T tests")
        for afe in df_104['AFE'].unique():
            df_afe = df_104.loc[df_104['AFE'] == afe]
            ax.errorbar(df_afe['DAQ_CH'], df_afe['Diff New_LN2T'], marker='o', markersize=3.5, capsize=2,linewidth=0 , elinewidth=0.6, color=color_list[afe] , label=f"Afe: {afe} ({df_afe['SIPM_type'].unique()[0]})")
        ax.set_xlabel('DAQ channel')
        ax.set_ylabel('Vbd diff New - LN2T (V)') 
        plt.xticks(ticks=df['DAQ_CH'])
        plt.grid(linewidth=0.3)
        plt.legend()
        plt.tight_layout()
        plt.savefig(f'{output_dir}/New_vs_LN2T/newln2t_diff_scatter.jpg', dpi=300)
        plt.close(fig)
        
    # Histogram: New - LN2T Vbd value (only endpoint 104)    
    if newln2t_diff_hist == 'yes':
        plt.hist(df_104['Diff New_LN2T'], bins=14,color='lime', edgecolor='black')
        plt.title("New endpoint 104\nChannel Vbd difference: New LAr IV results -  Coldbox LN2T tests")
        plt.xlabel("Vbd new - LN2T (V)")
        plt.ylabel("Counts")
        plt.savefig(f'{output_dir}/New_vs_LN2T/newln2t_diff_hist.jpg', dpi=300)
        plt.close()
        

    ##################################################################################
    ##################################################################################
    
    
    ''' Old vs LN2T data'''
    
    
    # Scatter plot: LN2T and Old Vbd value (only endpoint 104)
    if oldln2t_scatter == 'yes':    
        fig, axs = plt.subplots(3, 2, figsize=(10, 8))
        fig.delaxes(axs[2, 1]) 
        axs = np.ravel(axs)
        fig.suptitle(f"Old endpoint 104 \nChannel Vbd comparison: Old LAr IV results -  Coldbox LN2T tests")    
        for afe in df_104['AFE'].unique():
            df_afe = df_104.loc[df_104['AFE'] == afe]
            axs[afe].set_title(f'AFE {afe:.0f}')
            axs[afe].errorbar(df_afe['DAQ_CH'], df_afe['Old Vbd(V)'], yerr=0 , marker='o', markersize=3.5, capsize=2,linewidth=0 , elinewidth=0.6, color='red' , label=f'Old LAr')
            axs[afe].errorbar(df_afe['DAQ_CH']+0.1, df_afe['Coldbox_LN2T Vbd(V)'], yerr=0 , marker='o', markersize=3.5, capsize=2,linewidth=0 , elinewidth=0.6, color='orange' , label=f'LN2T')
            axs[afe].set_xlabel('DAQ channel')
            axs[afe].set_ylabel('Vbd (V)') 
            axs[afe].legend(fontsize=7)
            axs[afe].tick_params(axis='x', which='both', labelsize=5)
            axs[afe].tick_params(axis='y', labelsize=8)

        plt.tight_layout()
        plt.savefig(f'{output_dir}/Old_vs_LN2T/oldln2t_scatter_104.jpg', dpi=300)
        plt.close(fig)
    
    # Scatter plot: Old-LN2T Vbd difference 
    if oldln2t_diff_scatter == 'yes':   
        # Endpoint 104
        fig, ax = plt.subplots(1, figsize=(16, 7))
        fig.suptitle(f"Old Endpoint 104\nChannel Vbd difference: Old LAr IV results -  Coldbox LN2T tests")
        for afe in df_104['AFE'].unique():
            df_afe = df_104.loc[df_104['AFE'] == afe]
            ax.errorbar(df_afe['DAQ_CH'], df_afe['Diff Old_LN2T'], marker='o', markersize=3.5, capsize=2,linewidth=0 , elinewidth=0.6, color=color_list[afe] , label=f"Afe: {afe} ({df_afe['SIPM_type'].unique()[0]})")
        ax.set_xlabel('DAQ channel')
        ax.set_ylabel('Vbd diff Old - LN2T (V)') 
        plt.xticks(ticks=df['DAQ_CH'])
        plt.grid(linewidth=0.3)
        plt.legend()
        plt.tight_layout()
        plt.savefig(f'{output_dir}/Old_vs_LN2T/oldln2t_diff_scatter_104.jpg', dpi=300)
        plt.close(fig)
        
        # ALL - FBK vs HPK
        plt.figure(figsize=(12, 6))  
        plt.title('Channel Vbd difference: Old LAr IV results - Coldbox LN2T tests')   
        plt.grid(linewidth=0.5)
        colors = df['SIPM_type'].map({'FBK': 'red', 'HPK': 'blue'})
        plt.scatter(df['Stringa_DAQch'], df['Diff Old_LN2T'], color=colors, s=12)
        plt.xlabel('Endpoint_Channel', fontsize=10)
        plt.ylabel('Vbd Old - LN2T (V)', fontsize=10)
        plt.title('Difference Old - LN2T Vbd value')   
        plt.xticks(rotation=90, fontsize=4)
        legend_elements = [Line2D([0], [0], marker='o', color='w', markerfacecolor='red', markersize=8, label='FBK'),
                        Line2D([0], [0], marker='o', color='w', markerfacecolor='blue', markersize=8, label='HPK')]
        plt.legend(handles=legend_elements, title="SIPM_type")
        plt.tight_layout()  
        plt.savefig(f'{output_dir}/Old_vs_LN2T/oldln2t_diff_scatter_a.jpg', dpi=300)  
        plt.close()
        
        
        # ALL - Different End_AFE
        plt.figure(figsize=(12, 6))  
        plt.title('Channel Vbd difference: Old LAr IV results - Coldbox LN2T tests')   
        plt.grid(linewidth=0.5)
        df['End_AFE'] = df['End'].astype(str) + '_' + df['AFE'].astype(str)
        unique_combinations = df['End_AFE'].unique()
        palette = sns.color_palette("hsv", len(unique_combinations))  # Usa una palette continua di colori
        color_mapping = {combination: palette[i] for i, combination in enumerate(unique_combinations)}
        colors = df['End_AFE'].map(color_mapping)
        plt.scatter(df['Stringa_DAQch'], df['Diff Old_LN2T'], color=colors, s=12)
        plt.xlabel('Endpoint_Channel', fontsize=10)
        plt.ylabel('Vbd Old - LN2T (V)', fontsize=10)
        plt.title('Difference Old - LN2T Vbd value', fontsize=14)   
        plt.xticks(rotation=90, fontsize=4)
        legend_elements = [Line2D([0], [0], marker='o', color='w', markerfacecolor=palette[i], markersize=5, 
                            label=combination) for i, combination in enumerate(unique_combinations)]
        plt.legend(handles=legend_elements, title="AFE_End", ncol=2, fontsize=6, title_fontsize=8, loc='upper right')
        plt.tight_layout()  
        plt.savefig(f'{output_dir}/Old_vs_LN2T/oldln2t_diff_scatter_b.jpg', dpi=300)  
        plt.close()
        
    # Histogram: Old - LN2T Vbd value 
    if oldln2t_diff_hist == 'yes':
        # Endpoint 104    
        plt.hist(df_104['Diff Old_LN2T'], bins=14,color='orange', edgecolor='black')
        plt.title('New Endpoint 104\nChannel Vbd difference: Old LAr IV results - Coldbox LN2T tests')   
        plt.xlabel("Vbd Old - LN2T (V)")
        plt.ylabel("Counts")
        plt.savefig(f'{output_dir}/Old_vs_LN2T/oldln2t_diff_hist_104.jpg', dpi=300)
        plt.close()
        
        # ALL
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6))  

        ax1.hist(df[df['SIPM_type'] == 'FBK'].dropna(subset=['Coldbox_LN2T Vbd(V)'])['Diff Old_LN2T'], bins=9, color='skyblue', alpha=0.7, edgecolor='black')
        ax1.set_title('FBK SiPMs')
        ax1.set_xlabel('Vbd Old - LN2T (V)')
        ax1.set_ylabel('Counts')

        ax2.hist(df[df['SIPM_type'] == 'HPK'].dropna(subset=['Coldbox_LN2T Vbd(V)'])['Diff Old_LN2T'], bins=9, color='palegreen', alpha=0.7, edgecolor='black')
        ax2.set_title('HPK SiPMs')
        ax2.set_xlabel('Vbd Old - LN2T (V)')
        ax2.set_ylabel('Counts')

        fig.suptitle('Channel Vbd difference: Old LAr IV results - Coldbox LN2T tests')   
        plt.tight_layout()
        plt.savefig(f'{output_dir}/Old_vs_LN2T/oldln2t_diff_hist.jpg', dpi=300)  
        plt.close()
        
  
    

    
    
if __name__ == "__main__":
    main()