'''
Determination of the operation voltage
- Input: output.txt of Vbd_determination.py or Vbd_best.py
- Output: one json for endpoint + complete map

'''


import click, json
import numpy as np
import pandas as pd
from os import chdir, listdir, path, makedirs, getcwd

import warnings
from datetime import datetime

from IV_analysis_utils import *

def is_date_valid(file_name):
    match = re.search(r"([A-Za-z]{3}-\d{2}-\d{4})", file_name)
    if match:
        file_date = datetime.strptime(match.group(1), "%b-%d-%Y")
        return file_date >= datetime.strptime("Apr-19-2024", "%b-%d-%Y")
    return False


def check_header(file):
    header_output_file_1 = 'IP\tFile_name\tAPA\tAFE\tConfig_CH\tDAQ_CH\tSIPM_type\tRun\tEndpoint_timestamp\tStart_time\tEnd_time\tBias_data_quality\tBias_min_I\tBias_max_I\tVbd_bias(DAC)\tVbd_bias(V)\tVbd_bias_error(V)\tBias_conversion_slope\tBias_conversion_intercept\tTrim_data_quality\tTrim_min_I\tTrim_max_I\tFit_status\tPoly_Vbd_trim(DAC)\tPoly_Vbd_trim_error(DAC)\tPulse_Vbd_trim(DAC)\tPulse_Vbd_trim_error(DAC)\tVbd(V)\tVbd_error(V)\n'
    header_output_file_2 = 'IP\tAPA\tAFE\tConfig_CH\tDAQ_CH\tSIPM_type\tRuns\tBias_conversion_slope\tBias_conversion_intercept\tVbd(V)\tVbd_error(V)\n'
    with open(file, 'r') as ifile:
        first_line = ifile.readline()
        if  (first_line == header_output_file_1) or (first_line == header_output_file_2):
            return True
        else:
            return False




@click.command()
@click.option("--input_dir", 
              default= getcwd() + '/../../data/iv_analysis',
              help="Folder where all iv results are (default = 'PDS/data/iv_analysis' ")
@click.option("--run", 
              default= 'Jun-18-2024-run00',
              help="Run to analyze (default = 'Jun-18-2024-run00' ") 
@click.option("--input_filename", 
              default= 'output.txt',
              help="Name of the file you want to read, containing Vbd info (default = 'output.txt' ") 
@click.option("--output_dir", 
              default= None,
              help="Folder where results are saved (default: equal to the run input_dir)")
@click.option("--fbk-ov", 
              default=4.5, 
              help='Overvoltage for fbk (default: 4.5 V)')
@click.option("--hpk-ov", 
              default=3.0, 
              help='Overvoltage for hpk (default: 3.0 V)')
@click.option("--json-name", 
              default=None, 
              help="Name for the json file with operation voltage (default: 'dic_FBKxx_HPKyy')")


def main(input_dir, run, input_filename, output_dir, fbk_ov, hpk_ov, json_name):
    map_complete = {'10.73.137.104':{},'10.73.137.105':{},'10.73.137.107':{},'10.73.137.109':{},'10.73.137.111':{},'10.73.137.112':{},'10.73.137.113':{}}
    endpoint_list = ['104','105','107','109','111','112','113']
    
    if output_dir is None:
        output_dir = input_dir + '/' + run
    if json_name is None:
        json_name = f'dic_FBK('+(str(fbk_ov)).replace('.', ',') + 'V)_HPK(' +(str(hpk_ov)).replace('.', ',') +'V)' 

    directories = [d for d in listdir(f'{input_dir}/{run}') if (f'{input_dir}/{run}/{d}') and ('ip10.73.137.' in d)]
    for d in directories:
        ip = d.split('ip')[-1]
        id = int(ip[-1][-2:])
        apa = d.split('apa')[1][0]
        print(f'\n\n-------------------------- \n\n --- {ip} --- \n')
        chdir(f'{input_dir}/{run}/{d}')
        txt_files = [stringa for stringa in listdir() if stringa.endswith(input_filename)] 
        if len(txt_files) == 1:
            txt_file = txt_files[0]
            if check_header(txt_file):
                df = pd.read_csv(txt_file, delimiter='\t')

                FBK_CH = [] 
                FBK_Vop_bias_dac = [] 
                FBK_Vop_trim_dac = []
                HPK_CH = [] 
                HPK_Vop_bias_dac = [] 
                HPK_Vop_trim_dac = []

                for AFE in range(5):
                    print(f'\n-- AFE: {AFE:.0f} --\n')
                    df_afe = df[df['AFE'] == AFE]
                    Vop_trim_dac_list= []
                    
                    if len(df_afe) == 0: #If the afe is not used, continue
                        print('Not used')
                        continue
                        
                    elif df_afe['Vbd(V)'].isna().all():
                        print('Only NaN data')
                        Vop_bias_dac = np.nan
                        Vop_trim_dac_list = np.full(len(df_afe), np.nan).tolist()
                       
                    else:
                        if  df_afe['SIPM_type'].iloc[0] == 'FBK':
                            ov_V = fbk_ov
                        else:
                            ov_V = hpk_ov

                        mean_DAC_V_bias = [np.nanmean(df_afe['Bias_conversion_slope']),np.nanmean(df_afe['Bias_conversion_intercept'])] #Mean conversion coefficients
                        
                        Vop_max = np.nanmax(df_afe['Vbd(V)'])  + ov_V #Maximum operating voltage
                        Vop_bias_dac = VOLT_DAC_full_conversion(Vop_max, mean_DAC_V_bias)[0] #Maximum bias value -> BIAS DAC to set
                        Vop_bias_v = DAC_VOLT_bias_conversion(Vop_bias_dac,mean_DAC_V_bias)
                        print(f'Fixed bias: {Vop_bias_dac:.0f} DAC --> {Vop_bias_v:.3f} V\n')

                        for index, row in df_afe.iterrows():
                            if np.isnan(row['Vbd(V)']):
                                Vop = np.nan
                                Vop_trim_dac = np.nan
                            else:
                                Vop = row['Vbd(V)'] + ov_V #Operating voltage
                                Vop_trim_dac = int( (Vop_bias_v - Vop) / (4.4/4095.0) ) #Trim DAC to set
                                
                            Vop_trim_v = DAC_VOLT_trim_conversion(Vop_trim_dac)
                            Vop_applied = DAC_VOLT_full_conversion(Vop_bias_dac,Vop_trim_dac,mean_DAC_V_bias)

                            Vop_trim_dac_list.append(Vop_trim_dac)

                            print('Config channel: ' + str(row['Config_CH']) + ' \t DAQ channel: ' + str(row['DAQ_CH']))
                            print(f'Vop to set: {Vop:.3f} V --> Voltage applied: {Vop_applied:.3f} V')
                            print(f'Bias: {Vop_bias_dac:.0f} DAC --> {Vop_bias_v:.3f} V\tTrim: {Vop_trim_dac:.0f} DAC --> {Vop_trim_v:.3f} V')
                            if np.isnan(Vop_trim_dac):
                                print('Attention: Nan value for trim!! (Vbd was not found, fit problem or dead/disconnected')
                            if abs(Vop - Vop_applied) > 0.01:
                                print('Attention: too much different between Vop and applied voltage!!!!!')
                            print()

                    if df_afe['SIPM_type'].iloc[0] == 'FBK':
                        FBK_CH += df_afe[df_afe['SIPM_type'] == 'FBK']['Config_CH'].tolist()
                        FBK_Vop_bias_dac += [Vop_bias_dac] 
                        FBK_Vop_trim_dac += Vop_trim_dac_list
                    else:
                        HPK_CH += df_afe[df_afe['SIPM_type'] == 'HPK']['Config_CH'].tolist()
                        HPK_Vop_bias_dac += [Vop_bias_dac] 
                        HPK_Vop_trim_dac += Vop_trim_dac_list
                            
                # SINGLE ENDPOINT JSON FILE
                output_json = {} 
                
                output_json['ip'] = ip
                output_json['apa'] = apa
                output_json['run'] = run
                
                output_json['fbk_ov'] = fbk_ov
                output_json['fbk'] = FBK_CH
                output_json['fbk_op_bias'] = [int(x) if not np.isnan(x) else None for x in FBK_Vop_bias_dac]
                output_json['fbk_op_trim'] = [int(x) if not np.isnan(x) else None for x in FBK_Vop_trim_dac]
                
                output_json['hpk_ov'] = hpk_ov
                output_json['hpk'] = HPK_CH
                output_json['hpk_op_bias'] = [int(x) if not np.isnan(x) else None for x in HPK_Vop_bias_dac]
                output_json['hpk_op_trim'] = [int(x) if not np.isnan(x) else None for x in HPK_Vop_trim_dac]
                
                
                with open(f'{ip}_{json_name}.json', "w") as fp:
                    json.dump(output_json, fp) # Vbd=None means some error!!

                

                ch_list = FBK_CH + HPK_CH
                if ch_list != sorted(ch_list):
                    print('\nEndpoint ' + ip + '--> Attention: channel ordering!')
        
                bias_list = FBK_Vop_bias_dac + HPK_Vop_bias_dac
                while len(bias_list) < 5:
                    bias_list.append(0)
                
                trim_list = [0] * 40
            
                trim_data = FBK_Vop_trim_dac + HPK_Vop_trim_dac
        
                for i in range(len(ch_list)):
                    trim_list[ch_list[i]] = trim_data[i]
        
                index_none = [index for index, value in enumerate(trim_list) if np.isnan(value)]
                if len(index_none) > 0: 
                    print('\nEndpoint ' + ip + ' --> Attention: Config channels ' + ' '.join(map(str, index_none)) + ' have Vop_trim_value = NaN --> it was set to zero!')
                else:
                    print('\nEndpoint ' + ip + ' is okay!')
            
                trim_list = [0 if np.isnan(x) else x for x in trim_list]
            
                map_complete[ip]['id'] = id
                map_complete[ip]['apa'] = apa
                map_complete[ip]['ch']= ch_list
                map_complete[ip]['bias'] = bias_list
                map_complete[ip]['trim'] = trim_list
                map_complete[ip]['ov'] = {'fbk': fbk_ov, 'hpk': hpk_ov }
                map_complete[ip]['run'] = run


    print('\n\n')
    print(map_complete)

    chdir(f'{output_dir}')
    print()


    with open(f'{run}_{json_name}.json', "w") as fp:
        json.dump(map_complete, fp)

    for key, inner_dict in map_complete.items():
        if len(inner_dict) == 0:
            print(f'\nData about endpoint {key} not present! --> Incomplete json map!!\n')

    
    print('\n\nDONE\n\n')
######################################################################################

if __name__ == "__main__":
    main()
