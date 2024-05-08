import click, json
import numpy as np
from os import listdir, path
from uproot import open as op
from datetime import datetime
from scipy.optimize import curve_fit
from scipy.signal import savgol_filter
from matplotlib import pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from rich.progress  import track
import warnings
warnings.filterwarnings("ignore")
from iv_utl import *

@click.command()
@click.option("--in_dir",  default='/eos/experiment/neutplatform/protodune/experiments/ProtoDUNE-II/PDS_Commissioning/ivcurves/Mar-21-2024-run00', help='Input directory to look for data folders.')
@click.option("--ips",     default='ALL',  help='IP address to analyse. Default is ALL')
@click.option("--out_dir", default='SAME', help='Output directory to save the summary file. Default is SAME')

def iv_ana(in_dir, ips, out_dir, verbose = False):
    
    message =  '''
    This script generates a breakdown_output.txt file with the results for IV curves.

    Args:
        - in_dir (str): The directory where the root files are located. Default is '/eos/experiment/neutplatform/protodune/experiments/ProtoDUNE-II/PDS_Commissioning/ivcurves/Mar-21-2024-run00'.
    Example: python iv_analysis.py --in_dir /eos/experiment/neutplatform/protodune/experiments/ProtoDUNE-II/PDS_Commissioning/ivcurves/Mar-21-2024-run00

    Output:
        - IVplots.pdf with all acquired TRIM IV curves
        - output.txt with information about the Vbd determination 
        - dic.json with information about the operating voltage of each channel
    '''
    if verbose: print(message)

    map_file = "../maps/channel_map.json"

    with open(map_file, "r") as fp:
        channel_map = json.load(fp)  
    if verbose:
        print("Imported map from ",map_file,":")
        print(channel_map)

    Vdb_map = {"RT":{"FBK": 32.5, "HPK": 51}, "CT":{"FBK": 26.9, "HPK": 41.5}}

    #We create the output and logout files
    if out_dir == 'SAME': out_dir = in_dir
    output_file = open(f'{out_dir}/{out_dir.split("/")[-1]}_fit.txt', 'w') # Output File
    logout_file = open(f'{out_dir}/log.txt', 'w') # Logout File
    output_file.write(f"IP\tFile\tAPA\tAFE\tCH\tSIPM\tSlope[V/DAC]\tIntercept[V]\tVbd(Suggested)\tVbd(Pulse)\tVbd(Poly)\tStatus\n")
    # output_file.write(f'IP\tFile_name\tEndpoint_timestamp\tStart_time\tEnd_time\tSIPM_type\tBias_data_quality\tBias_min_I\tBias_max_I\tVbd_bias(DAC)\tVbd_bias(V)\tVbd_bias_error(V)\tBias_conversion_slope\tBias_conversion_intercept\tTrim_data_quality\tTrim_min_I\tTrim_max_I\tFit_status\tPoly_Vbd_trim(DAC)\tPoly_Vbd_trim_error(DAC)\tPulse_Vbd_trim(DAC)\tPulse_Vbd_trim_error(DAC)\tVbd(V)\tVbd_error(V)\n')
    pdf_pages = PdfPages(f'{out_dir}/{out_dir.split("/")[-1]}_IVplots.pdf')

    # List of folders in the directory (ignoring ipython folder)
    folders = sorted([folder for folder in listdir(f'{in_dir}') if path.isdir(f'{in_dir}/{folder}')])
    folders = filter(lambda x: not x.startswith('.'), folders)

    if ips == 'ALL': print('Analysing all endpoints')
    elif ips.isdigit() and len(ips) == 3: folders = [item for item in folders if item.endswith(ips)]; print(f'Analysing endpoint {ips}')
    else: print("Invalid endpoint"); return
    
    directory=''; trees = []
    #Cycle on endpoint_folders in the input directory
    for f,folder in enumerate(folders):
        # Check the date of the data
        timestamp_string = f"{(folder.split('/')[-1]).split('_')[0]}_{(folder.split('/')[-1]).split('_')[1]}" #Ex run
        timestamp = datetime.strptime(timestamp_string, '%b-%d-%Y_%H%M')
        if timestamp <  datetime(2024, 4, 19) and f==0: print('\033[91mData previous to 19th April 2024 takend with wrong V range; computing 2nd Vbd point.\033[0m')

        # Get the run number, IP address and the sipm type
        apa = int((folder.split('/')[-1].split('apa')[-1]).split('_')[0])
        ip = (folder.split('/')[-1]).split('ip')[-1]

        dic = channel_map[ip]
        fbk = channel_map[ip]['fbk']
        hpk = channel_map[ip]['hpk']

        # To save information of each channel, divided by AFE
        DAC_V_bias_AFE = [[[],[]], [[],[]], [[],[]], [[],[]], [[],[]]] 
        sipm_AFE = [[], [], [], [], []]
        chan_AFE = [[], [], [], [], []]
        VbdV_AFE = [[], [], [], [], []] 
        Vbd_bias_dac_AFE = [[], [], [], [], []]
        Vbd_trim_dac_AFE = [[], [], [], [], []]
        has_trim = False; has_bias = False

        logout_file.write(f'\n\n--------------------------------------------------------------- \nBIAS scan and Trim IV CURVE analysis \n\nENDPOINT: {ip} \t {timestamp} \n\n')
        files = sorted(listdir(f"{in_dir}/{folder}")) # List of files in the folder
        for my_file in track(files, description=f'Analysing {folder}...'): # Loop over the files
            if my_file.endswith('.root'): # Check if the file is a root file

                ch = int(my_file.split('.root')[0].split('ch_')[-1])
                afe =  ch//8
                sipm = 'FBK' if ch in fbk else 'HPK'
                iv_dataset = iv_data(ip,apa,afe,ch,sipm)

                sipm_AFE[afe].append(sipm)
                
                # General dictionary independent from the root file structure
                root_file = op(f'{in_dir}/{folder}/{my_file}')
                if f == 0 and ch == 0: #Only doing this for the first root file to save time
                    directory, trees = get_tree_info(root_file)
                    logout_file.write(f'In this configuration you have TDirectories: {directory}, TTrees: {trees}\n')
                array_dict = {}
                for tree in trees:
                    tree = tree.split(";1")[0]
                    path_to_var = f'{directory.split(";1")[0]}/{tree}'
                    for var in root_file[path_to_var].keys():
                        array_dict[f'{tree}/{var}'] = root_file[path_to_var+"/"+var].array(library="np")
                
                #Breakdown voltage determination (TRIM AND BIAS INDEPENDLY)
                if 'iv_trim/current' in array_dict.keys():
                    if f==0 and ch==0: has_trim = True; print("We have the iv_trim/current data :)")
                    curr = np.flip(array_dict['iv_trim/current'])*(-1)
                    status_quality = data_quality(data=curr,bias_mode=has_bias); 
                if 'bias/current' in array_dict.keys(): 
                    if f==0 and ch==0: has_bias = True; print("And bias/current data!!")
                    curr = array_dict['bias/current']*(-1)
                    status_quality = data_quality(data=curr,bias_mode=has_bias)
                else: 
                    if f==0 and ch==0: print(f'No bias/current nor iv_trim/current data found. Check {array_dict.keys()}')
                    return

                #If the data is bad, we don't do anything
                # if 'BAD' in status_quality: 
                #     print('BAD DATA')
                #     Vbd_trim = Vbd_pulse = Vbd_poly = 0
                #     status_quality = status_quality.split('BAD')[1]
                                    
                # #If the data is good, we do two fits if bias/current is present, one otherwise
                # else:
                iv_dataset.trim_curr = array_dict['iv_trim/current'] * (-1)
                # We shift current to positive values
                if(any(value<0 for value in iv_dataset.trim_curr)): iv_dataset.trim_curr = iv_dataset.trim_curr - min(iv_dataset.trim_curr)
                iv_dataset.trim_volt = (-array_dict['iv_trim/trim'] * (4.4/4095.0)) + array_dict['bias/bias_v'][-1]

                # DAC -> VOLT bias conversion (linear fit)
                DAC_V_bias_conversion,covar = curve_fit(linear_function, array_dict['bias/bias_dac'], array_dict['bias/bias_v'])
                DAC_V_bias_conversion_error = np.sqrt(np.diag(covar))

                # Bias Vbd to VOLT
                Vbd_bias_dac = int(array_dict['bias/bias_dac'][len(array_dict['bias/bias_dac'])-1])
                Vbd_bias_V   = DAC_VOLT_bias_conversion(Vbd_bias_dac,DAC_V_bias_conversion)
                Vbd_bias_V_error = np.sqrt((Vbd_bias_V*DAC_V_bias_conversion_error[0])**2+(DAC_V_bias_conversion_error[1])**2)

                # status_quality = data_quality(data=curr,bias_mode=bias)
                Vbd_trim, Vbd_puls, Vbd_poly, status_quality, PulseShape_trim, Polynomial_trim = Vbd_determination(iv_dataset.trim_volt,iv_dataset.trim_curr)

                #If we do not have bias_current data we cannot use it
                iv_dataset.bias_dac  = array_dict['bias/bias_dac']
                iv_dataset.bias_volt = array_dict['bias/bias_v']

                if has_bias: 
                    iv_dataset.bias_curr = array_dict['bias/current']*(-1)
                    Vbd_bias, Vbd_puls, Vbd_poly, status_quality, PulseShape_bias, Polynomial_bias = Vbd_determination(iv_dataset.bias_volt,iv_dataset.bias_curr)
                
                if 'PulseShape_bias' not in locals(): 
                    Vbd_bias = 0; Vdb_puls = 0; Vbd_poly = 0
                    status_quality = "WARNING: No bias/current data available"
                    PulseShape_bias = [0,0,[[0],[0]],[[0],[0]],[0,0]]
                    Polynomial_bias = [0,0,[[0],[0]],[[0],[0]],[0,0]]

                iv_subplots(filename=my_file, pdf_pages=pdf_pages,iv_dataset=iv_dataset,
                            dac2v=[DAC_V_bias_conversion[0],DAC_V_bias_conversion[1]],
                            PulseShape_trim=PulseShape_trim, Polynomial_trim=Polynomial_trim, 
                            PulseShape_bias=PulseShape_bias, Polynomial_bias=Polynomial_bias)

                #DAC - VOLT convesion to estimate the breakdown voltage (V)
                # Vbd_V = DAC_VOLT_full_conversion(Vbd_bias, Vbd_trim, DAC_V_bias_conversion) #TODO: Fix this
                Vbd_V = 0
                Vbd_V_error = 0 # TODO: Define this

                chan_AFE[afe].append(ch)
                sipm_AFE[afe].append(sipm)
                VbdV_AFE[afe].append(Vbd_V)
                Vbd_trim_dac_AFE[afe].append(Vbd_trim)
                Vbd_bias_dac_AFE[afe].append(Vbd_bias)
                #Save information per AFE
                DAC_V_bias_AFE[afe][0].append(DAC_V_bias_conversion[0])
                DAC_V_bias_AFE[afe][1].append(DAC_V_bias_conversion[1])
                Vbd_bias_dac_AFE[afe].append(Vbd_bias)
                Vbd_trim_dac_AFE[afe].append(Vbd_trim)
                            
                #Print information 
                logout_file.write(f'Quality: {status_quality}\n')
                logout_file.write(f'Channel: {ch:.0f} \t {sipm}\n')
                logout_file.write(f'Bias: {Vbd_bias_dac:.0f} DAC --> {Vbd_bias_V:.3f} +/- {Vbd_bias_V_error:.3f} V\n')
                logout_file.write(f'Vbd : {Vbd_V:.3f} +/- {Vbd_V_error:.3f} V\n')

                # bias_AFE[afe].append(int(array_dict['bias/bias_dac'][len(array_dict['bias/bias_dac'])-1]))
                # bias_vol_AFE[afe].append(array_dict['bias/bias_v'][len(array_dict['bias/bias_v'])-1]) 
                
                # save_output = f"{ip_address}\tfile:{files[j]}\tSiPM: {sipm} Status: {status} Vbd_TRIM(DAC) = {Vbd_trim}" 
                save_output = f"{ip}\t{my_file}\t{apa}\t{afe}\t{ch}\t{sipm}\t{DAC_V_bias_conversion[0]}\t{DAC_V_bias_conversion[1]}\t{Vbd_trim}\t{Vbd_puls}\t{Vbd_poly}\t{status_quality}\n"
                output_file.write(save_output)

        # #To determine the BIAS and TRIM (in terms of DAC) to set, taking into account Overvoltage  #TODO: Fix this
        # FBK_op_bias_dac = [] 
        # FBK_op_trim_dac = []
        # HPK_op_bias_dac = [] 
        # HPK_op_trim_dac = []

        # print('\n\n -- Determination of SiPM operating voltage --')

        # for AFE in range(5):
        #     logout_file.write(f'\n\n------------- \nAFE: {AFE:.0f}')
        #     op_trim_dac_list= []
            
        #     if len(chan_AFE[AFE]) == 0: #If the afe is not used, continue
        #         logout_file.write('Not used')
        #         continue
                
        #     elif all(np.isnan(x) for x in Vbd_bias_dac_AFE[AFE]) or (all(np.isnan(x) for x in Vbd_trim_dac_AFE[AFE])) or (all(np.isnan(x) for x in VbdV_AFE[AFE])): #If all data about an afe are nan, returns nan
        #         logout_file.write('Only NaN data')
        #         op_bias_dac = np.nan
        #         op_trim_dac_list = np.full(len(chan_AFE[AFE]), np.nan).tolist()
                
        #     else:
        #         if sipm_AFE[AFE][0] == 'FBK': ov_V = 4.5
        #         else: ov_V = 3

        #         mean_DAC_V_bias = [np.nanmean(DAC_V_bias_AFE[AFE][0]),np.nanmean(DAC_V_bias_AFE[AFE][1])] #Mean conversion coefficients

        #         list_noNaN = [x for x in Vbd_bias_dac_AFE[AFE] if not np.isnan(x)]
        #         if np.allclose(list_noNaN, list_noNaN[0]):
        #             logout_file.write('Same Bias\n')
        #             Vov_bias_dac, Vov_trim_dac, Vov_set = VOLT_DAC_full_conversion(ov_V, mean_DAC_V_bias)
        #             op_bias_dac = list_noNaN[0] + Vov_bias_dac
        #             op_bias_v = DAC_VOLT_bias_conversion(op_bias_dac,mean_DAC_V_bias)
                    
        #             for i in range(len(chan_AFE[AFE])):
        #                 if np.isnan(Vbd_bias_dac_AFE[AFE][i]) or np.isnan(Vbd_trim_dac_AFE[AFE][i]):
        #                     Vop = np.nan
        #                     op_trim_dac = np.nan 
        #                 else:
        #                     Vop = VbdV_AFE[AFE][i] + ov_V
        #                     op_trim_dac = Vov_trim_dac + Vbd_trim_dac_AFE[AFE][i]

        #                 logout_file.write(f'Channel: {chan_AFE[AFE][i]:.0f}')
        #                 logout_file.write(f'Vop to set (Vbd+Vov): {Vop:.3f} V --> Voltage applied: {DAC_VOLT_full_conversion(op_bias_dac,op_trim_dac,mean_DAC_V_bias):.3f} V')
        #                 logout_file.write(f'Bias: {op_bias_dac:.0f} DAC --> {op_bias_v:.3f} V')
        #                 logout_file.writeint(f'Trim: {op_trim_dac:.0f} DAC --> {DAC_VOLT_trim_conversion(op_trim_dac):.3f} V\n')
        #                 op_trim_dac_list.append(int(op_trim_dac))
                    
        #         else:
        #             logout_file.write('Different Bias\n')
        #             VOP_max = np.nanmax(VbdV_AFE[AFE])  + ov_V #Maximum operating voltage
        #             op_bias_dac = VOLT_DAC_full_conversion(VOP_max, mean_DAC_V_bias)[0] #Maximum bias value -> BIAS DAC to set
        #             op_bias_v = DAC_VOLT_bias_conversion(op_bias_dac,mean_DAC_V_bias)
        #             #print(f'Fixed bias: {op_bias_dac:.0f} DAC --> {op_bias_v:.3f} V\n')

        #             for i in range(len(chan_AFE[AFE])):
        #                 if np.isnan(VbdV_AFE[AFE][i]):
        #                     V_op = np.nan
        #                     op_trim_dac = np.nan
        #                 else:
        #                     V_op = VbdV_AFE[AFE][i] + ov_V #Operating voltage
        #                     op_trim_dac = int( (op_bias_v - V_op) / (4.4/4095.0) ) #Trim DAC to set

        #                 logout_file.write(f'Channel: {chan_AFE[AFE][i]:.0f}')
        #                 logout_file.write(f'Vop to set: {V_op:.3f} V --> Voltage applied: {DAC_VOLT_full_conversion(op_bias_dac,op_trim_dac,mean_DAC_V_bias):.3f} V')
        #                 logout_file.write(f'Bias: {op_bias_dac:.0f} DAC --> {op_bias_v:.3f} V')
        #                 logout_file.write(f'Trim: {op_trim_dac:.0f} DAC --> {DAC_VOLT_trim_conversion(op_trim_dac):.3f} V\n')
        #                 op_trim_dac_list.append(int(op_trim_dac))
                

        #     if sipm_AFE[AFE][0] == 'FBK':
        #         FBK_op_bias_dac += [op_bias_dac] 
        #         FBK_op_trim_dac += op_trim_dac_list
        #     else:
        #         HPK_op_bias_dac += [op_bias_dac] 
        #         HPK_op_trim_dac += op_trim_dac_list


        # # JSON FILE
        # # Since JSON file doesn't support NaN, i convert it to None
        # dic['FBK_op_bias'] = [x if not np.isnan(x) else None for x in FBK_op_bias_dac]
        # dic['FBK_op_trim'] = [x if not np.isnan(x) else None for x in FBK_op_trim_dac]
        # dic['HPK_op_bias'] = [x if not np.isnan(x) else None for x in HPK_op_bias_dac]
        # dic['HPK_op_trim'] = [x if not np.isnan(x) else None for x in HPK_op_trim_dac]
        # dic['timestamp'] = timestamp_string
        
        # # Vbd=None means some error!!
        # with open(f'{in_dir}/{str(folder)}/{ip_address}_dic.json', "w") as fp: json.dump(dic, fp) 
                
    output_file.close()
    logout_file.close()
    pdf_pages.close()                

if __name__ == "__main__": iv_ana()