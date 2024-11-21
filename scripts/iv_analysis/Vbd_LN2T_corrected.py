import numpy as np
import pandas as pd
from os import chdir, listdir, path, makedirs, getcwd


def daq_channel_conversion(ch_config):
    afe = int(ch_config//8)
    return 10*(afe) + (ch_config - afe*8)

def calcola_vbd_ln2t_diff(row):
    if pd.isna(row['Coldbox_LN2T Vbd(V)']):
        print(f"Missing LN2T value : IP {row['IP']} - Config_CH {row['Config_CH']} ")
        return row['New Vbd(V)']
    elif row['SIPM_type'] == 'FBK':
        return row['Coldbox_LN2T Vbd(V)'] + diff_fbk
    elif row['SIPM_type'] == 'HPK':
        return row['Coldbox_LN2T Vbd(V)'] + diff_hpk
    else:
        return None  



def main():
    df = pd.read_csv('/afs/cern.ch/user/a/anbalbon/IV_curve/PDS/data/iv_analysis/Comparison_plots/dataset.csv')

    global diff_fbk
    global diff_hpk
    diff_fbk = (df[(df['Diff Old_LN2T'].notna()) & (df['SIPM_type'] == 'FBK')])['Diff Old_LN2T'].mean()
    diff_hpk = (df[(df['Diff Old_LN2T'].notna()) & (df['SIPM_type'] == 'HPK')])['Diff Old_LN2T'].mean()

    print(f'fbk : {diff_fbk:.3f} V')
    print(f'hpk : {diff_hpk:.3f} V')
    

    df['Vbd LN2T + diff'] = df.apply(calcola_vbd_ln2t_diff, axis=1) 


    
    name_run = 'Vbd_LN2T_corrected'
    dir = f'/afs/cern.ch/user/a/anbalbon/IV_curve/PDS/data/iv_analysis/Vbd_LN2T_corrected'
    if not path.exists(dir):
        makedirs(dir)
    
    for ip in df['IP'].unique().tolist():
            print(f'\n\n --- ENDPOINT {ip} --- \n')
            df_ip = df[df['IP'] == ip]
            apa = df_ip['APA'].unique().tolist()[0] 
    
            dir_ip = f'{dir}/apa{apa}_ip{ip}'
            if not path.exists(dir_ip):
                makedirs(dir_ip)
    
            text_file = open(f'{dir_ip}/{ip}_output.txt', 'w') # Fit info
            text_file.write(f'IP\tAPA\tAFE\tConfig_CH\tDAQ_CH\tSIPM_type\tRun\tBias_conversion_slope\tBias_conversion_intercept\tVbd(V)\tVbd_error(V)\n')
            
            for ch in df_ip['Config_CH'].unique().tolist():
                df_ch = df_ip[df_ip['Config_CH'] == ch]
                afe = df_ch['AFE'].unique().tolist()[0] 
                sipm = df_ch['SIPM_type'].unique().tolist()[0] 
                mean_bias_conversion_slope = df_ch['Bias_conversion_slope'].tolist()[0] 
                mean_bias_conversion_intercept = df_ch['Bias_conversion_intercept'].tolist()[0] 
                mean_Vbd = df_ch['Vbd LN2T + diff'].tolist()[0] 
                std_Vbd = 0
                
                print(f'Config_CH {ch} --> Vbd_mean = {mean_Vbd:.3f} +/- {std_Vbd:.3f} V \n')
    
                text_file.write(f"{ip}\t{apa}\t{afe}\t{ch}\t{daq_channel_conversion(ch)}\t{sipm}\t[{name_run}]\t{mean_bias_conversion_slope:.5f}\t{mean_bias_conversion_intercept:.5f}\t{mean_Vbd:.4f}\t{std_Vbd:.4f}\n")
        
            text_file.close()
    
        
if __name__ == "__main__":
    main()