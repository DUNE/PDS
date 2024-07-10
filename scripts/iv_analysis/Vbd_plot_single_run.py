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
    DATA_df = read_data(input_dir,run)  
    print('\nALL DATA READ\n')  

    if (plot_type.upper() == 'CH_VBD_X_RUN') or (plot_type.upper() == 'ALL'):
        print('Plot of Vbd as a function of channel number, for a given run')
        DATA_df = DATA_df.dropna(subset=['Vbd(V)'])
        if run == 'ALL':
            pdf_CH_VBD_all = PdfPages(f'{output_dir}/CH_VBD_plot_all.pdf')
        if run == 'ALL':
            run_list = DATA_df['Run'].unique()
        else:
            run_list = [run]
        for run_data in run_list:
            run_check = ''
            df_run = DATA_df.loc[DATA_df['Run'] == run_data]
            if len(df_run) == 0:
                df_run = DATA_df[~DATA_df['Run'].isin([item for item in run_list if item != run_data])]
            if path.exists(f"{output_dir}/{df_run['RunFolder'].iloc[0]}"):
                pdf_CH_VBD_single = PdfPages(f"{output_dir}/{df_run['RunFolder'].iloc[0]}/CH_VBD_plot.pdf")
            else:
                pdf_CH_VBD_single = PdfPages(f"{output_dir}/{df_run['RunFolder'].iloc[0]}_CH_VBD_plot.pdf")

            df_run_completed = full_map_dataframe(df_run, run_data)    

            fig, ax = plt.subplots(1, figsize=(16, 7))
            fig.suptitle(f"Channel Vbd \n RUN: {df_run['RunFolder'].iloc[0]}")
            i=0
            for ip in df_run_completed['IP'].unique():
                df_ip = df_run_completed.loc[df_run_completed['IP'] == ip]
                ax.errorbar(df_ip['Stringa_DAQch'], df_ip['Vbd(V)'], yerr=df_ip['Vbd_error(V)'] , marker='o', markersize=3.5, capsize=2,linewidth=0 , elinewidth=0.6, color=color_list[i] , label=f'Endpoint: {ip}')
                i+=1
            ax.set_xlabel('DAQ channel')
            ax.set_ylabel('Vbd (V)') 
            plt.xticks(rotation=90, fontsize=5)
            plt.grid(linewidth=0.3)
            plt.legend()
            plt.tight_layout()
            pdf_CH_VBD_single.savefig(fig)
            if run == 'ALL':
                pdf_CH_VBD_all.savefig(fig)
            plt.close(fig)
            
            pdf_CH_VBD_single.close()
        if run == 'ALL':
            pdf_CH_VBD_all.close()
    
    

    if (plot_type.upper() == 'VB_HIST_X_RUN') or (plot_type.upper() == 'ALL'):
        print('Histogram of Vbd grouped by endpoint number, for a given run')
        DATA_df = DATA_df.dropna(subset=['Vbd(V)'])
        if run == 'ALL':
            run_list = DATA_df['Run'].unique()
        else:
            run_list = [run]
        for run_data in run_list:
            df_run = DATA_df.loc[DATA_df['Run'] == run_data]
            if len(df_run) == 0:
                df_run = DATA_df[~DATA_df['Run'].isin([item for item in run_list if item != run_data])]
            if path.exists(f"{output_dir}/{df_run['RunFolder'].iloc[0]}"):
                pdf_VBD_hist = PdfPages(f"{output_dir}/{df_run['RunFolder'].iloc[0]}/VBD_histogram.pdf")
            else:
                pdf_VBD_hist = PdfPages(f"{output_dir}/{df_run['RunFolder'].iloc[0]}_VBD_histogram.pdf")

            fig, axs = plt.subplots(1, 2, figsize=(10, 8))
            fig.suptitle(f"Vbd histogram \n RUN:{df_run['RunFolder'].iloc[0]}")
            axs = np.ravel(axs)
            for i, sipm in enumerate(['HPK','FBK']):
                df_run_sipm = df_run.loc[df_run['SIPM_type'] == sipm]
                VB_HIST_X_RUN(axs[i], df_run_sipm, sipm)
            
            plt.tight_layout()
            pdf_VBD_hist.savefig(fig)
            plt.close(fig)
            
            pdf_VBD_hist.close()


if __name__ == "__main__":
    main()