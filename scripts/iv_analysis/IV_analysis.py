'''
IV analysis

'''


# sistema fit polinomial!!

import click, json
import numpy as np
from os import chdir, listdir, path, makedirs
from uproot import open as op
from scipy.optimize import curve_fit
from scipy.signal import savgol_filter
import matplotlib
from matplotlib import pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import warnings
from datetime import datetime
warnings.filterwarnings("ignore", category=matplotlib.MatplotlibDeprecationWarning)
#warnings.filterwarnings("ignore", category=OptimizeWarning)

from IV_analysis_utils import *

@click.command()
@click.option("--input_dir", default='/eos/experiment/neutplatform/protodune/experiments/ProtoDUNE-II/PDS_Commissioning/ivcurves/May-09-2024-run00') #Run folder
@click.option("--output_dir", default='/afs/cern.ch/user/a/anbalbon/IV_curve/PDS/data/iv_analysis') #Where to save data
@click.option("--endpoint", default='ALL') #ALL or 104,105,107,109,111,112,113
@click.option("--trimfit", default='poly') #poly or pulse or both 
@click.option("--map_path", default='/afs/cern.ch/user/a/anbalbon/IV_curve/PDS/maps/original_channel_map.json') #update json map (without dead channels)
def main(input_dir, output_dir, endpoint, trimfit, map_path):
    with open(map_path, 'r') as file:
        map = json.load(file)
    
    chdir(input_dir)

    # Where to save data
    run =input_dir.split('/')[-1]
    run_dir_output = output_dir+'/'+run
    if not path.exists(run_dir_output):
        makedirs(run_dir_output)
        
    ENDPOINT_FOLDERS = sorted(listdir()) #List of folders in the input directory, each one is realetd to an endpoint
    if endpoint.isdigit() and len(endpoint) == 3:
        ENDPOINT_FOLDERS = [item for item in ENDPOINT_FOLDERS if item.endswith(endpoint)]
    
    for endpoint_folder in ENDPOINT_FOLDERS: #Cycle on endpoint_folders in the input directory
        if len(endpoint_folder) > 40:
            timestamp_stringa = f"{(endpoint_folder.split('/')[-1]).split('_')[0]}_{(endpoint_folder.split('/')[-1]).split('_')[1]}" #Ex run
            timestamp = datetime.strptime(timestamp_stringa, '%b-%d-%Y_%H%M')
            ip_address = (endpoint_folder.split('/')[-1]).split('ip')[-1]
            endpoint = ip_address[-3:]
            apa = int((endpoint_folder.split('/')[-1].split('apa')[-1]).split('_')[0])

            if timestamp <  datetime(2024, 4, 19):
                print('Wrong data, before 19th April 2024')
                continue
            else:
                #Good data format - after 19th April 2024
                dic = map[ip_address]
    
                # To save information of each channel, divided by AFE
                DAC_V_bias_AFE = [[[],[]], [[],[]], [[],[]], [[],[]], [[],[]]] 
                sipm_AFE = [[], [], [], [], []]
                channel_AFE = [[], [], [], [], []]
                Vbd_bias_dac_AFE = [[], [], [], [], []]
                Vbd_trim_dac_AFE = [[], [], [], [], []]
                Vbd_V_AFE = [[], [], [], [], []] 
                bias_dac_AFE = [[], [], [], [], []]
                current_bias_AFE = [[], [], [], [], []]

                # Output file for plots 
                endpoint_dir_output = run_dir_output+'/'+endpoint_folder
                if not path.exists(endpoint_dir_output):
                    makedirs(endpoint_dir_output)
            
                text_file = open(f'{endpoint_dir_output}/{ip_address}_output.txt', 'w') # Fit info
                pdf_file_NEW = PdfPages(f'{endpoint_dir_output}/{ip_address}_plots.pdf') # NEW
                text_file.write(f'IP\tFile_name\tAPA\tAFE\tConfig_CH\tDAQ_CH\tSIPM_type\tRun\tEndpoint_timestamp\tStart_time\tEnd_time\tBias_data_quality\tBias_min_I\tBias_max_I\tVbd_bias(DAC)\tVbd_bias(V)\tVbd_bias_error(V)\tBias_conversion_slope\tBias_conversion_intercept\tTrim_data_quality\tTrim_min_I\tTrim_max_I\tFit_status\tPoly_Vbd_trim(DAC)\tPoly_Vbd_trim_error(DAC)\tPulse_Vbd_trim(DAC)\tPulse_Vbd_trim_error(DAC)\tVbd(V)\tVbd_error(V)\n')
                
                

                print(f'\n\n ---------------------------------------------------------------  \n\nENDPOINT: {ip_address} \t {timestamp} \n\n')
                chdir(f"{input_dir}/{str(endpoint_folder)}")
                FILES = [] #List of files in the endpoint_folder selected
                for file in listdir(): #Cycle on root file in the selected endpoint folder
                    if file[len(file)-4:] == 'root':
                        FILES.append(file)

                print('-- BIAS scan and Trim IV CURVE analysis --\n')
                for ch in dic['fbk']+dic['hpk']:
                    file_name = 'apa_' + str(apa) + '_afe_' + str(ch//8) + '_ch_' + str(ch) + '.root' #root filename we should have
                    afe = int(ch//8)
                    if ch in dic['fbk']:
                        sipm = 'FBK'
                        Vbd_roomT = 32.5 #V
                        Vbd_ln2T = 26.9 #V
                    else:
                        sipm = 'HPK'
                        Vbd_roomT = 51 #V
                        Vbd_ln2T = 41.5 #V
                        
                    if file_name in FILES: #Check if the file is present 
                        root_file = op(file_name)
                        start_time = root_file["tree/run/time_start"].array()[0]
                        end_time = root_file["tree/run/time_end"].array()[0]

                        ''' 
                        Vbd BIAS determination + conversion (from DAC to VOLT) 
                        '''
                        bias_dac = np.array(root_file["tree/bias/bias_dac"])
                        bias_V = np.array(root_file["tree/bias/bias_v"])
                        bias_c = np.array(root_file["tree/bias/current"]) *(-1)


                        bias_dac_AFE[afe].append(bias_dac) 
                        current_bias_AFE[afe].append(bias_c)

                        bias_status = bias_data_quality(bias_c)
                        if bias_status == 'Good':
                            # DAC -> VOLT bias conversio (linear fit)
                            DAC_V_bias_conversion, covariance = curve_fit(linear_function, np.array(bias_dac), np.array(bias_V))
                            DAC_V_bias_conversion_errors = np.sqrt(np.diag(covariance))

                            # Bias Vbd
                            Vbd_bias_dac = int(bias_dac[len(bias_dac)-1])
                            Vbd_bias_V = DAC_VOLT_bias_conversion(Vbd_bias_dac,DAC_V_bias_conversion)
                            Vbd_bias_V_error = np.sqrt((Vbd_bias_V*DAC_V_bias_conversion_errors[0])**2+(DAC_V_bias_conversion_errors[1])**2)

                            
                            '''                  
                            Vbd TRIM determination
                            '''
                            #trim_c = (root_file["tree/iv_trim/current"].array())[::-1]  *(-1) #current flip
                            trim_c_original = np.array(root_file["tree/iv_trim/current"]) *(-1) 
                            trim_c = trim_c_original + abs(min(trim_c_original)) # Shift (to have only positive currents)
                            trim_dac = np.array(root_file["tree/iv_trim/trim"])
                  
                            trim_status = trim_data_quality(trim_c)
                            if trim_status == 'Good':        
                                # First Savitzky–Golay filter on trim current
                                sgf_IV_degree = 1
                                sgf_IV_window = 10
                                step = np.diff(trim_dac)[0]
                                
                                c_filtered = [savgol_filter(trim_c, sgf_IV_window, sgf_IV_degree), sgf_IV_window, sgf_IV_degree] #Filtered current with information on the filter
                                der_c =  derivative_cactus(trim_dac, c_filtered[0]) #First normalized derivative of filtered current

                                #Remove Nan or Inf data
                                mask = ~np.isnan(der_c) & ~np.isinf(der_c)
                                der_trim = trim_dac[mask]
                                der_c = der_c[mask]

                                if (trimfit == 'poly') or (trimfit == 'both') :
                                    #Polynomial Fit
                                    sgf_poly = [2*sgf_IV_window, 2]
                                    Polynomial = IV_Polynomial(der_trim, der_c, sgf_poly)

                                    
                                    while (np.isnan(Polynomial[0]) and (sgf_poly[0]>10)):
                                        sgf_poly[0] -= 2 ######## ATTENZIONE!!!!
                                        Polynomial = IV_Polynomial(der_trim, der_c, sgf_poly)
                                    sgf_poly[0] = 2*sgf_IV_window
                                    
                                    while (np.isnan(Polynomial[0]) and (sgf_poly[0]<40)):
                                        sgf_poly[0] += 2 
                                        Polynomial = IV_Polynomial(der_trim, der_c, sgf_poly)
                                    
                                    
                                    

                                    PulseShape = [np.nan,np.nan, [0,0],[0,0],[0,0]]
                            
                                if (trimfit == 'pulse') or (trimfit == 'both') :
                                    #Pulse shape Fit
                                    sgf_pulse = [2, 1]
                                    PulseShape = IV_PulseShape(der_trim, der_c, step, sgf_pulse)
                                    while (np.isnan(PulseShape[0]) and (sgf_pulse[0]<10)):
                                        sgf_pulse[0] += 2
                                        PulseShape = IV_PulseShape(der_trim, der_c, step, sgf_pulse)  

                                    Polynomial = [np.nan,np.nan,[0,0],[0,0],[0,0]]
                                
                                                        
                            else: #If the file is not present
                                c_filtered = [0, 0, 0]
                                Polynomial = [np.nan,np.nan,[0,0],[0,0],[0,0]]
                                PulseShape = [np.nan,np.nan, [0,0],[0,0],[0,0]]


                            #Check the results for Vbd trim (DAC)
                            Vbd_trim_dac_poly = Vbd_trim_dac_pulse = np.nan
                            if (not np.isnan(Polynomial[0])) and (not np.isnan(PulseShape[0])): #Both methods works
                                Vbd_trim_dac_poly = float(Polynomial[0])
                                Vbd_trim_dac_pulse = float(PulseShape[0]) 
                                Vbd_trim_dac = round(int((Vbd_trim_dac_pulse + Vbd_trim_dac_poly)/2))
                                Vbd_trim_dac_error = abs(Delta)/2 #To be estimated...
                                Delta = Vbd_trim_dac_pulse - Vbd_trim_dac_poly
                                if abs(Delta) < 200 : 
                                    trim_fit_status = 'Both good' #If both method works and the results are quite similar
                                else:
                                    trim_fit_status = f'Check(Delta={Delta:.0f})' # If both method works but the results are very different
                            elif (not np.isnan(Polynomial[0])) and (np.isnan(PulseShape[0])): #Only polyfit result
                                Vbd_trim_dac = Vbd_trim_dac_poly = float(Polynomial[0])
                                Vbd_trim_dac_error = float(Polynomial[1])
                                if trimfit == 'both' : 
                                    trim_fit_status = 'Pulsefit failed'
                                elif trimfit == 'poly':
                                    trim_fit_status = 'Only polyfit'
                            elif (not np.isnan(PulseShape[0])) and (np.isnan(Polynomial[0])): #Only pulsefit result
                                Vbd_trim_dac = Vbd_trim_dac_pulse = float(PulseShape[0])
                                Vbd_trim_dac_error = float(PulseShape[1]) #To be estimated
                                if trimfit == 'both' : 
                                    trim_fit_status = 'Pulsefit failed'
                                elif trimfit == 'pulse':
                                    trim_fit_status = 'Only pulsefit'
                            else: #If no results
                                Vbd_trim_dac = np.nan
                                Vbd_trim_dac_error = np.nan
                                if trimfit == 'both' : 
                                    trim_fit_status = 'Both failed'
                                elif trimfit == 'poly':
                                    trim_fit_status = 'Polyfit failed'
                                elif trimfit == 'pulse':
                                    trim_fit_status = 'Pulsefit failed'
    
                            Vbd_trim_dac_poly_error = Polynomial[1]
                            Vbd_trim_dac_pulse_error = PulseShape[1]
                            
                            #DAC - VOLT convesion to estimate the breakdown voltage (V)
                            Vbd_V = DAC_VOLT_full_conversion(Vbd_bias_dac, Vbd_trim_dac, DAC_V_bias_conversion)
                            Vbd_V_error = np.sqrt(DAC_VOLT_trim_conversion(Vbd_trim_dac_error)**2 + Vbd_bias_V_error**2)
                            
                           
                            text_file.write(f'{ip_address}\t{file_name}\t{apa:.0f}\t{afe:.0f}\t{ch:.0f}\t{daq_channel_conversion(ch):.0f}\t{sipm}\t{run}\t{timestamp_stringa}\t{start_time}\t{end_time}\t{bias_status}\t{min(bias_c):.3f}\t{max(bias_c):.3f}\t{Vbd_bias_dac}\t{Vbd_bias_V:.3f}\t{Vbd_bias_V_error:.3f}\t{DAC_V_bias_conversion[0]:.5f}\t{DAC_V_bias_conversion[1]:.3f}\t{trim_status}\t{min(trim_c_original):.3f}\t{max(trim_c_original):.3f}\t{trim_fit_status}\t{Vbd_trim_dac_poly:.0f}\t{Vbd_trim_dac_poly_error:.0f}\t{Vbd_trim_dac_pulse:.0f}\t{Vbd_trim_dac_pulse_error:.0f}\t{Vbd_V:.3f}\t{Vbd_V_error:.3f}\n')
                            
                            
                            #Save information per AFE
                            DAC_V_bias_AFE[afe][0].append(DAC_V_bias_conversion[0])
                            DAC_V_bias_AFE[afe][1].append(DAC_V_bias_conversion[1])
                            sipm_AFE[afe].append(sipm)
                            channel_AFE[afe].append(ch)
                            Vbd_V_AFE[afe].append(Vbd_V)
                            Vbd_bias_dac_AFE[afe].append(Vbd_bias_dac)
                            Vbd_trim_dac_AFE[afe].append(Vbd_trim_dac)
    
                            
                            #Print information 
                            print(f'Channel: {ch:.0f} \t {sipm}')
                            print(f'Bias: {Vbd_bias_dac:.0f} DAC --> {Vbd_bias_V:.3f} +/- {Vbd_bias_V_error:.3f} V')
                            print(f'Poly: {Polynomial[0]:.0f} +/- {Polynomial[1]:.0f} DAC')
                            print(f'Pulse: {PulseShape[0]:.0f} +/- {PulseShape[1]:.0f} DAC')
                            print(f'Vbd : {Vbd_V:.3f} V')
                            print()

                            plot_production(pdf_file_NEW, endpoint,apa,afe,ch,sipm,bias_status,bias_dac,bias_V,bias_c,DAC_V_bias_conversion,trim_dac,trim_c,trim_status,c_filtered,Polynomial,PulseShape)
                           
        
                        else:
                            print(f'Bias scan error: {file_name} \n')
                            plot_production(pdf_file_NEW, endpoint,apa,afe,ch,sipm,bias_status,bias_dac,bias_V,bias_c,[np.nan,np.nan],np.nan,np.nan,np.nan,np.nan,np.nan,np.nan)

                            
                            text_file.write(f'{ip_address}\t{file_name}\t{apa:.0f}\t{afe:.0f}\t{ch:.0f}\t{daq_channel_conversion(ch):.0f}\t{sipm}\t{run}\t{timestamp_stringa}\t{start_time}\t{end_time}\t{bias_status}\t{min(bias_c):.3f}\t{max(bias_c):.3f}\t{np.nan}\t{np.nan}\t{np.nan}\t{np.nan}\t{np.nan}\t{np.nan}\t{np.nan}\t{np.nan}\t{np.nan}\t{np.nan}\t{np.nan}\t{np.nan}\t{np.nan}\t{np.nan}\t{np.nan}\n')

                                                    
                            DAC_V_bias_AFE[afe][0].append(np.nan)
                            DAC_V_bias_AFE[afe][1].append(np.nan)
                            sipm_AFE[afe].append(sipm)
                            channel_AFE[afe].append(ch)
                            Vbd_V_AFE[afe].append(np.nan)
                            Vbd_bias_dac_AFE[afe].append(np.nan)
                            Vbd_trim_dac_AFE[afe].append(np.nan)

                    
                    else:
                        print(f'Missing file: {file_name}\n')
                        plot_production(pdf_file_NEW, endpoint,apa,afe,ch,sipm,None,np.nan,np.nan,np.nan,[np.nan,np.nan],np.nan,np.nan,np.nan,np.nan,np.nan,np.nan)
                        
                        text_file.write(f'{ip_address}\t{file_name}\t{apa:.0f}\t{afe:.0f}\t{ch:.0f}\t{daq_channel_conversion(ch):.0f}\t{sipm}\t{run}\t{timestamp_stringa}\tMissing_file\t{np.nan}\t{np.nan}\t{np.nan}\t{np.nan}\t{np.nan}\t{np.nan}\t{np.nan}\t{np.nan}\t{np.nan}\t{np.nan}\t{np.nan}\t{np.nan}\t{np.nan}\t{np.nan}\t{np.nan}\t{np.nan}\t{np.nan}\t{np.nan}\t{np.nan}\n')

                        
    
                        DAC_V_bias_AFE[afe][0].append(np.nan)
                        DAC_V_bias_AFE[afe][1].append(np.nan)
                        sipm_AFE[afe].append(sipm)
                        channel_AFE[afe].append(ch)
                        Vbd_V_AFE[afe].append(np.nan)
                        Vbd_bias_dac_AFE[afe].append(np.nan)
                        Vbd_trim_dac_AFE[afe].append(np.nan)
                        bias_dac_AFE[afe].append([]) 
                        current_bias_AFE[afe].append([])
 
                
                pdf_file_NEW.close()
                text_file.close()

                
                pdf_file_bias_AFE = PdfPages(f'{endpoint_dir_output}/{ip_address}_Bias_IVplots_AFE.pdf')
                plot_IVbias_AFE(pdf_file_bias_AFE,endpoint,apa,sipm_AFE,bias_dac_AFE, current_bias_AFE, Vbd_bias_dac_AFE, channel_AFE)
                pdf_file_bias_AFE.close()
               
                
                #To determine the BIAS and TRIM (in terms of DAC) to set, taking into account Overvoltage 
                FBK_op_bias_dac = [] 
                FBK_op_trim_dac = []
                HPK_op_bias_dac = [] 
                HPK_op_trim_dac = []

                print('\n\n -- Determination of SiPM operating voltage --')
    
                for AFE in range(5):
                    print(f'\n\n------------- \nAFE: {AFE:.0f}\n')
                    op_trim_dac_list= []
                    
                    if len(channel_AFE[AFE]) == 0: #If the afe is not used, continue
                        print('Not used')
                        continue
                        
                    elif all(np.isnan(x) for x in Vbd_bias_dac_AFE[AFE]) or (all(np.isnan(x) for x in Vbd_trim_dac_AFE[AFE])) or (all(np.isnan(x) for x in Vbd_V_AFE[AFE])): #If all data about an afe are nan, returns nan
                        print('Only NaN data')
                        op_bias_dac = np.nan
                        op_trim_dac_list = np.full(len(channel_AFE[AFE]), np.nan).tolist()
                       
                    else:
                        if sipm_AFE[AFE][0] == 'FBK':
                            ov_V = 4.5
                        else:
                            ov_V = 3

                        mean_DAC_V_bias = [np.nanmean(DAC_V_bias_AFE[AFE][0]),np.nanmean(DAC_V_bias_AFE[AFE][1])] #Mean conversion coefficients

                        list_noNaN = [x for x in Vbd_bias_dac_AFE[AFE] if not np.isnan(x)]
                        if np.allclose(list_noNaN, list_noNaN[0]):
                            print('Same Bias\n')
                            Vov_bias_dac, Vov_trim_dac, Vov_set = VOLT_DAC_full_conversion(ov_V, mean_DAC_V_bias)
                            op_bias_dac = list_noNaN[0] + Vov_bias_dac
                            op_bias_v = DAC_VOLT_bias_conversion(op_bias_dac,mean_DAC_V_bias)
                            
                            for i in range(len(channel_AFE[AFE])):
                                if np.isnan(Vbd_bias_dac_AFE[AFE][i]) or np.isnan(Vbd_trim_dac_AFE[AFE][i]):
                                    Vop = np.nan
                                    op_trim_dac = np.nan 
                                else:
                                    Vop = Vbd_V_AFE[AFE][i] + ov_V
                                    op_trim_dac = Vov_trim_dac + Vbd_trim_dac_AFE[AFE][i]
    
                                print(f'Channel: {channel_AFE[AFE][i]:.0f}')
                                print(f'Vop to set (Vbd+Vov): {Vop:.3f} V --> Voltage applied: {DAC_VOLT_full_conversion(op_bias_dac,op_trim_dac,mean_DAC_V_bias):.3f} V')
                                print(f'Bias: {op_bias_dac:.0f} DAC --> {op_bias_v:.3f} V')
                                print(f'Trim: {op_trim_dac:.0f} DAC --> {DAC_VOLT_trim_conversion(op_trim_dac):.3f} V\n')
                                op_trim_dac_list.append(op_trim_dac)
                            
                        else:
                            print('Different Bias\n')
                            VOP_max = np.nanmax(Vbd_V_AFE[AFE])  + ov_V #Maximum operating voltage
                            op_bias_dac = VOLT_DAC_full_conversion(VOP_max, mean_DAC_V_bias)[0] #Maximum bias value -> BIAS DAC to set
                            op_bias_v = DAC_VOLT_bias_conversion(op_bias_dac,mean_DAC_V_bias)
                            #print(f'Fixed bias: {op_bias_dac:.0f} DAC --> {op_bias_v:.3f} V\n')
        
                            for i in range(len(channel_AFE[AFE])):
                                if np.isnan(Vbd_V_AFE[AFE][i]):
                                    V_op = np.nan
                                    op_trim_dac = np.nan
                                else:
                                    V_op = Vbd_V_AFE[AFE][i] + ov_V #Operating voltage
                                    op_trim_dac = int( (op_bias_v - V_op) / (4.4/4095.0) ) #Trim DAC to set
    
                                print(f'Channel: {channel_AFE[AFE][i]:.0f}')
                                print(f'Vop to set: {V_op:.3f} V --> Voltage applied: {DAC_VOLT_full_conversion(op_bias_dac,op_trim_dac,mean_DAC_V_bias):.3f} V')
                                print(f'Bias: {op_bias_dac:.0f} DAC --> {op_bias_v:.3f} V')
                                print(f'Trim: {op_trim_dac:.0f} DAC --> {DAC_VOLT_trim_conversion(op_trim_dac):.3f} V\n')
                                op_trim_dac_list.append(op_trim_dac)
                       
    
                    if sipm_AFE[AFE][0] == 'FBK':
                        FBK_op_bias_dac += [op_bias_dac] 
                        FBK_op_trim_dac += op_trim_dac_list
                    else:
                        HPK_op_bias_dac += [op_bias_dac] 
                        HPK_op_trim_dac += op_trim_dac_list
    
    
                # JSON FILE
                output_json = {key: dic[key] for key in dic if key in ['apa','fbk','hpk']} #Per pulire la mappa
                
                # Since JSON file doesn't support NaN, i convert it to None
                output_json['FBK_op_bias'] = [int(x) if not np.isnan(x) else None for x in FBK_op_bias_dac]
                output_json['FBK_op_trim'] = [int(x) if not np.isnan(x) else None for x in FBK_op_trim_dac]
                output_json['HPK_op_bias'] = [int(x) if not np.isnan(x) else None for x in HPK_op_bias_dac]
                output_json['HPK_op_trim'] = [int(x) if not np.isnan(x) else None for x in HPK_op_trim_dac]
                output_json['timestamp'] = timestamp_stringa
                output_json['run'] = run
                output_json['ip'] = ip_address
                

                
                with open(f'{endpoint_dir_output}/{ip_address}_dic.json', "w") as fp:
                    json.dump(output_json, fp) # Vbd=None means some error!!

                

######################################################################################

if __name__ == "__main__":
    main()
