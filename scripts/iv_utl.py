## FUNCTIONS USED FOR THE IV CURVE ANALYSIS ##

import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import savgol_filter
from scipy.optimize import curve_fit
import warnings
warnings.filterwarnings("ignore")


def get_tree_info(root_file, debug=False):
    '''
    Function which returns the list of directories and trees of a root file
    
    Args:
        root_file (uproot.rootio.ROOTDirectory): root file to be read
        debug     (bool):                        if True, the debug mode is activated (default: False)

    Returns:
        directory (list(str)): list of directories (i.e ["solarnuana", "myanalysis;1"] with as many directories as you root file has)
        tree      (list(str)): list of trees (i.e ["Pandora_Output;1", "MCTruthTree;1", "SolarNuAnaTree;1"] with as many trees as you root file has)
    '''

    directory = [i for i in root_file.classnames() if root_file.classnames()[i]=="TDirectory"]
    if debug: print("The input root file has a TDirectory: " + str(directory))
    if len(directory) != 1: print("The input root file has more than one TDirectory, we are taking just the first one")
    tree      = [i.split("/")[1] for i in root_file.classnames() if root_file.classnames()[i]=="TTree"]
    if debug: print("The input root file has %i TTrees: "%len(tree) +str(tree))

    return directory[0],tree


def derivative_anna(x, y):
    dx = np.diff(x)
    dy = np.diff(y)
    return np.append(dy/dx,0) #/y

def derivative(y): return np.nan_to_num(np.gradient(y)/y) 
def derivative_cactus(x,y): return -np.gradient(np.log(y), x)
def linear_function(x, m, b): return m * x + b
def parabolic_function(x,a,b,c): return a*x*x + b*x + c

def fit_pulse(t, t0, T, A, P):
    x = (np.array(t) - t0+T)/T
    return P+A*np.power(x, 3)*np.exp(3*(1-x))

def data_quality(data,bias_mode):
    '''
    Check the quality of the data set. Errors are returned if:
        - the trim sample is smaller than 20,
        - all there are more than 10 NaN values 
        - the current range is lower than 0.2

    It returns a string:
        - Good if data are okay and we can procede with the analysis
        - Error / Warning associated to the data acquired
    '''
    if bias_mode:
        if len(data) < 10: return 'BAD [<10 samples]'
        elif (np.count_nonzero(np.isnan(data)) >= 10): return 'BAD [>10 NaN curr]'
        if (max(data) - min(data)) < 0.05 : return 'BAD [bias current]'
        return 'Good'

    else:
        if len(data) < 20: return 'BAD [<20 samples]'
        if np.count_nonzero(np.isnan(data)) == len(data): return 'BAD [all curr NaN]'
        elif (np.count_nonzero(np.isnan(data)) >= 10): return 'BAD [>10 NaN curr]'
        elif (np.count_nonzero(np.isnan(data)) > 0) and (np.count_nonzero(np.isnan(data)) < 10):
            return 'Good [WARNING: NaN curr values]' 
        if (max(data)-min(data)) < 0.2: return 'BAD [trim current]'
        return 'Good'
    
def standarisize_data(root_keys,volt,curr):
    '''
    Function to standarize the data. It returns the data in the correct format
    '''

    print('Standarize data')

def IV_Polynomial(x, der, sgf):
    '''
    2nd degree polynomial fit of the trim IV curve
    It returns an array of three element:
    -  Vbd trim from IV curve fit 
    -  Error on Vbd trim (fit error)
    -  An array with trim and filtered derivative used for the fit
    -  An array with x and y  coordinante to reconstruct the fitting function 
    -  An array with information of the savgol filter (window and degree)
    '''

    #Savgol filter on 1st normalized derivative
    window_length = min(sgf[0], len(der))
    y = savgol_filter(x=der, window_length=window_length, polyorder=sgf[1])
    if np.count_nonzero(np.isnan(y)) == len(y): return [np.nan, np.nan, [0, 0], [0,0], sgf]

    #Search for the maximum of first filtered derivative
    peak_index = np.argmax(y)

    #Select few points around the peak (more than 5 is ok)
    half_point_range = (len(x)) // 12  # 6 seems okay+
    if half_point_range < 5: half_point_range = 5
    min_index = peak_index - half_point_range
    if min_index < 0: min_index = 0
    max_index = peak_index + half_point_range 
    if max_index < 0: max_index = len(x)-1

    #Parabolic fit
    poly2_coeff, poly2_cov = curve_fit(parabolic_function, x[min_index:max_index], y[min_index:max_index])
    poly2_errors = np.sqrt(np.diag(poly2_cov))
    x_poly2 = np.linspace(x[0], x[-1], 100) 
    y_poly2 = y_values = np.polyval(poly2_coeff, x_poly2)
    # Vbd = x_poly2[np.argmax(y_poly2)]
    Vbd = -poly2_coeff[1] / (2*poly2_coeff[0])
    Vbd_error = np.sqrt((poly2_errors[1]/(2*poly2_coeff[0]))**2 + (poly2_coeff[1]*poly2_errors[0]/(2*poly2_coeff[0]*poly2_coeff[0]))**2)
    return [Vbd, Vbd_error, [x, y], [x_poly2, y_poly2], sgf]
        
def IV_PulseShape(x, der, sgf):
    '''
    Pulse Shape fit of the trim IV curve
    Args:
        - x   (array): x coordinate of the IV curve
        - der (array): 1st normalized derivative of the IV curve
        - sgf (array): array with the window and degree of the savgol filter
    Returns:
        An array of three element:
        -  Vbd trim from IV curve fit 
        -  An array with trim and filtered derivative used for the fit
        -  An array with x and y coordinante to reconstruct the fitting function 
        -  An array with information of the savgol filter (window and degree)
    '''

    print('Pulse Shape fit')
    #Savgol filter on 1st normalized derivative
    x = x/100
    y = savgol_filter(x=der, window_length=sgf[0], polyorder=sgf[1])
    #Search for the peak
    n_cut = len(x) // 2  # Dynamic n_cut after the second half of the plot
    window_size = min(20, len(x))  # Dynamic window size
    peak = savgol_filter(y, window_size, 2)[n_cut:]
    index = (np.argmax(peak) + n_cut) - min(3, len(peak) // 10)  # Dynamic constant
    #Choosing boundaries values for the fitting
    delta = len(x) - index
    boundary_offset = min(5, delta, index)
    min_guess = x[max(0, index - boundary_offset)]
    max_guess = x[min(len(x) - 1, index + boundary_offset)]

    #Fit using a pulse shape function
    start_index = np.where(x == min_guess)[0][0] + min(4, len(x) // 10)
    end_index = min(index + 25, len(x) - 1)
    x_pulse = np.arange(x[start_index], x[end_index], 0.01)

    # try:
    popt, pcov = curve_fit(fit_pulse, x[index:], y[index:], bounds=([min_guess, 0, 0, -0.5], [max_guess, min(100, np.max(y)), min(100, np.max(y)), 0.5]))
    y_pulse = fit_pulse(x_pulse, popt[0], popt[1], popt[2], popt[3])

    # print("Pulse fit",popt)
    # print("Pulse fit error",np.sqrt(np.diag(pcov)))
    # print("Pulse fit x",x_pulse)
    # print("Pulse fit y",y_pulse)

    return [popt[0], np.sqrt(np.diag(pcov))[0], [x*100, y], [x_pulse*100, y_pulse], sgf]
    #Check if the fit is good
    # if (len(y_pulse) < 2) or (y_pulse[0]==y_pulse.max()) or (y_pulse[-1]==y_pulse.max()) or (np.max(y_pulse) > min(5, len(y) // 10) * np.max(y[index:])):
    #     return [np.nan, np.nan, [0, 0], [0, 0], sgf]
    # else:
    #     Vbd = popt[0]*100
    #     Vbd_error = (np.sqrt(np.diag(pcov))[0])*100

    #     if (Vbd > 100) and (Vbd < x.max()*100-100):
    #         return [Vbd, Vbd_error, [x*100, y], [x_pulse*100, y_pulse], sgf]
    #     else:
    #         return [np.nan, np.nan, [0, 0], [0, 0], sgf]
    # except:
    #     return [np.nan, np.nan, [0, 0], [0, 0], sgf]

def Vbd_determination(volt,curr):
    
    # First filter
    savgol_window = (len(volt)) // 15  # 5 seems okay
    if (savgol_window < 4) and (savgol_window > 0): savgol_window = 4
    if (savgol_window == 0):                        savgol_window = 2
    curr_sav = savgol_filter(x=curr, window_length=savgol_window, polyorder=1)
    # Relative derivative
    # 1der_curr_sav = np.nan_to_num(np.gradient(curr_sav)/curr_sav)
    der1_curr_raw = [i / j for i, j in zip(derivative_anna(volt, curr), curr)]
    der1_curr_sav = [i / j for i, j in zip(derivative_anna(volt, curr_sav), curr_sav)]
    # First Savitzky–Golay filter on trim current
    sgf_puls = [2, 1]
    sgf_poly = [3*savgol_window, 2]

    # PulseShape = IV_PulseShape(x=volt, der=der1_curr_sav, sgf=sgf_puls)
    Polynomial = IV_Polynomial(x=volt, der=der1_curr_sav, sgf=sgf_poly)
    # Vbd_puls = float(PulseShape[0])
    Vbd_puls = 0
    Vbd_poly = float(Polynomial[0])
    Delta = abs(Vbd_puls - Vbd_poly)
    # print("VBD",Vbd_poly)
    Vbd_aver = Vbd_poly
    # if   np.isnan(Vbd_puls): Vbd_trim = Vbd_poly
    # # elif np.isnan(Vbd_poly): Vbd_trim = 0
    # # else:                    Vbd_trim = int((Vbd_puls + Vbd_poly)/2)
    # else: Vbd_trim = 0
    status_quality = "good_data_set"


    # if Vbd_pulse != 0 and Vbd_poly != 0 and Delta < 200:
    #     # We can change it depending on the performance comparison
    #     Vbd_trim = int((Vbd_pulse + Vbd_poly)/2)
    #     status_quality = "Good data set"
    # elif Vbd_pulse != 0 and Vbd_poly != 0 and Delta >= 200:
    #     Vbd_trim = Vbd_pulse = Vbd_poly = 0
    #     status_quality = f"ERROR: The Difference between the Vbd_poly and Vbd_pulse is too large ({Delta})."
    # elif Vbd_pulse == 0 and Vbd_poly != 0:
    #     Vbd_trim = int(Vbd_poly)
    #     status_quality = "WARNING: the pulse shape fitting method failled, please check the plots."
    # elif Vbd_pulse != 0 and Vbd_poly == 0:
    #     Vbd_trim = int(Vbd_pulse)
    #     status_quality = "WARNING: the polynomial fitting method failled, please check the plots."
    # else:
    #     Vbd_trim = Vbd_pulse = Vbd_poly = 0
    #     status_quality = "ERROR: Both fitting methods failed."
    
    return Vbd_aver, Vbd_puls, Vbd_poly, status_quality, [0,0,[[0],[0]],[[0],[0]],[0,0]], Polynomial
    # return Vbd_aver, Vbd_puls, Vbd_poly, status_quality, PulseShape, Polynomial


def DAC_VOLT_bias_conversion(bias_dac, bias_conversion):
    '''  Bias conversion: from DAC to VOLT '''
    if np.isnan(bias_dac): return np.nan
    else: return bias_conversion[0]*bias_dac + bias_conversion[1]

def DAC_VOLT_trim_conversion(trim_dac):
    '''  Trim conversion: from DAC to VOLT '''
    if np.isnan(trim_dac): return np.nan
    else: return trim_dac * (4.4/4095.0)

def DAC_VOLT_full_conversion (bias_dac, trim_dac, bias_conversion):
    '''  To obtain VOLTS from TRIM and BIAS in DAC'''
    if np.isnan(bias_dac) or np.isnan(trim_dac): return np.nan
    else: return DAC_VOLT_bias_conversion(bias_dac,bias_conversion) - DAC_VOLT_trim_conversion(trim_dac)

def VOLT_DAC_full_conversion (V_volt, bias_conversion):
    ''' From VOLTS, to DAC BIAS and TRIM to set (integer counts) '''
    bias_dac = int( (V_volt - bias_conversion[1])/bias_conversion[0]) + 2 #Integer number of DAC counts for BIAS
    bias_V = DAC_VOLT_bias_conversion(bias_dac,bias_conversion)
    trim_dac = int ((bias_V - V_volt) / (4.4/4095.0)) #Integer number of DAC counts for TRIM
    trim_V = DAC_VOLT_trim_conversion(trim_dac)
    V_volt_set = bias_V - trim_V
    if (trim_dac < 0) or (trim_dac > 4090) or (abs(V_volt_set-V_volt)>0.1):
        print('VOLT - DAC Error conversion')
        return np.nan,np.nan,np.nan
    else:
        return bias_dac, trim_dac, V_volt_set

def plot_trim(trim_status, trim, current, c_filtered, Polynomial, PulseShape):
    '''  To create the plot of the Trim IV curve, with fit results (if fit works) '''
    fig, ax = plt.subplots(figsize=(8,6))
    ax.set_xlabel("Trim (DAC)")
    ax.set_ylabel("Current") #Unit of measure(?)
    #ax.set_yscale('log')
    ax.scatter(trim, current, marker='o',s=5, color='blue', label='Acquired Trim IV curve')
    
    if trim_status == 'Good':
        ax.scatter(trim, c_filtered[0], marker='o',s=5, color='deepskyblue', label=f'Filtered IV curve SGF(w={c_filtered[1]:.0f}, d={c_filtered[2]:.0f})')
        
        ax_twin = ax.twinx()
        ax_twin.set_ylabel('Normalized Derivative')
        ax_twin.scatter(trim,derivative_cactus(trim,c_filtered[0]), marker='o', s=5, color='orange', label='Derivative of filtered data') 
        #ax_twin.set_ylim([min(derivative_cactus(trim,c_filtered[0]))*0.3, max(derivative_cactus(trim,c_filtered[0]))*2])

        if not np.isnan(Polynomial[0]): # Polynomial fit
            ax_twin.scatter(Polynomial[2][0],Polynomial[2][1], marker='o', s=5, color='mediumseagreen', label=f'Filtered derivative for Polyfit SGF(w={Polynomial[4][0]:.0f}, d={Polynomial[4][1]:.0f})')
            ax_twin.plot(Polynomial[3][0],Polynomial[3][1],color='green', label = '2nd polyfit')
            ax_twin.axvline(x=Polynomial[0], color='lime' ,linestyle='--', label= r'Poly trim $V_{bd}$* = '+f'{Polynomial[0]:.0f} +/- {Polynomial[1]:.0f} (DAC)')
            #ax_twin.set_ylim([min(Polynomial[2][1])*0.3, max(Polynomial[2][1])*2])
        
        if not np.isnan(PulseShape[0]): # Pulse shape fit 
            ax_twin.scatter(PulseShape[2][0], PulseShape[2][1], marker='o', s=5, color='violet', label=f'Filtered derivative for Pulse fit SGF(w={PulseShape[4][0]:.0f}, d={PulseShape[4][1]:.0f})')
            ax_twin.plot(PulseShape[3][0], PulseShape[3][1],color='purple', label = 'Pulse fit')
            ax_twin.axvline(x=PulseShape[0], color='fuchsia' ,linestyle='--', label= r'Pulse trim $V_{bd}$* = '+f'{PulseShape[0]:.0f} +/- {PulseShape[1]:.0f} (DAC)')
        
    
        ax_twin.legend(loc='upper right',fontsize='7')
        
    ax.legend(loc='center right',fontsize='7')
    return fig


def plot_bias(bias, current):
    '''  To create the plot of the Bias IV curve  '''
    Vbd_bias = bias[-1]
    fig, ax = plt.subplots(figsize=(8,6))
    ax.set_xlabel("Bias (DAC)")
    ax.set_ylabel("Current") #Unit of measure(?)
    #ax.set_yscale('log')
    ax.scatter(bias, current, marker='o',s=5, color='blue', label='Acquired Bias IV curve')
    ax.axvline(x=Vbd_bias, color='red' ,linestyle='--', label= r'Bias $V_{bd}$* = '+f'{Vbd_bias:.0f} (DAC)')
    ax.legend(loc='center left',fontsize='7')
    return fig
    

def plot_bias_trim(bias, current_bias, bias_conversion, trim, current_trim):
    '''
    To create the plot of the whole IV curve (trim and bias) in terms of volts
    '''
    bias_v = bias_conversion[0]*np.array(bias) + bias_conversion[1] 
    print("__________________________")
    print("__________________________")
    print(bias_v)
    print(np.array(trim))
    print("__________________________")
    print("__________________________")
    trim_v = bias_v[-1] - np.array(trim) * (4.4/4095.0)
    fig, ax = plt.subplots(figsize=(8,6))
    ax.set_xlabel("Volt")
    ax.set_ylabel("Current") #Unit of measure(?)
    #ax.set_yscale('log')
    ax.scatter(bias_v, current_bias, marker='o',s=5, color='blue', label='Acquired Bias IV curve')
    ax.scatter(trim_v, current_trim, marker='o',s=5, color='red', label='Acquired Trim IV curve')
    ax.legend(loc='center left',fontsize='7')
    return fig

def plot_IVbias_AFE(bias_list, current_list, Vbd_list, channels):
    '''   To create the plot of Bias IV curve for each AFE '''
    fig, ax = plt.subplots(figsize=(8,6))
    ax.set_xlabel("Bias (DAC)")
    ax.set_ylabel("Current") #Unit of measure(?)
    #ax.set_yscale('log')
    color_list = ['red','blue','green','purple','orange','grey','aqua','violet']
    for i in range(len(bias_list)):
        if len(bias_list[i]) > 0:
            ax.scatter(bias_list[i], current_list[i], marker='o',s=5, color=color_list[i], label=f'Channel: {channels[i]:.0f}')
            #ax.plot(bias_list[i], current_list[i], color=color_list[i], label=f'Channel: {channels[i]:.0f}')
            #ax.axvline(x=Vbd_list[i], color=color_list[i] ,linestyle='--', label= r'Bias $V_{bd}$ = '+f'{Vbd_list[i]:.0f} (DAC)')
    ax.legend(loc='center left',fontsize='7')
    return fig

    
def iv_subplots(filename,ip,pdf_pages,array_dict,dac2v,PulseShape_trim,PulseShape_bias,Polynomial_trim,Polynomial_bias):
    '''
    Function to create the IV curve plots for a single channel.
    It creates a 2x2 subplot with the following plots:
    - Bias Voltage vs Bias DAC
    - Current vs Trim Voltage
    - Derivative of the current vs Trim Voltage
    - Derivative of the current vs Trim Voltage with the fit results
    ''' 

    slope = dac2v[0]; intercept = dac2v[1]
    bias_dac = array_dict['bias/bias_dac']
    bias_v = array_dict['bias/bias_v']
    #trim_volt = array_dict['iv_trim/trim'] *slope + intercept
    print(bias_v[-1])
    print(bias_v)
    trim_volt = (-array_dict['iv_trim/trim'] * (4.4/4095.0)) + bias_v[-1]
    print(trim_volt)
    trim_curr = np.flip(array_dict['iv_trim/current'])
    fit_bias = False
    if 'bias/current' in array_dict.keys(): 
        fit_bias = True
        bias_curr = array_dict['bias/current']
        bias_curr = bias_curr*(-1)
        trim_curr = np.flip(trim_curr)*(-1)
        Vbd_puls_bias, Vbd_error_puls_bias, puls_filter_bias, puls_2nd_bias, puls_sgf_bias = PulseShape_bias
        Vbd_poly_bias, Vbd_error_poly_bias, poly_filter_bias, poly_2nd_bias, poly_sgf_bias = Polynomial_bias
    apa = (filename.split('.root')[0].replace('apa_','')).split('_')[0]
    ch  = int(filename.split('.root')[0].split('ch_')[-1])
    afe =  ch//8

    Vbd_puls_trim, Vbd_error_puls_trim, puls_filter_trim, puls_2nd_trim, puls_sgf_trim = PulseShape_trim
    Vbd_poly_trim, Vbd_error_poly_trim, poly_filter_trim, poly_2nd_trim, poly_sgf_trim = Polynomial_trim

    # Create a figure with all the subplots
    fig, axs = plt.subplots(2,2, figsize=(15,10))

    axs[0,0].scatter(bias_dac,bias_v,label=f'y=mx+n\nm={slope:0.2f} [V/DAC]\nn={intercept:0.2f} [V]',color="teal")
    axs[0,0].set_title(f'CONVERSION - IP:{ip} APA: {apa} AFE: {afe} CH: {ch}')
    axs[0,0].set_xlabel('Bias Voltage [DAC]')
    axs[0,0].set_ylabel('Bias Voltage [V]')
    axs[0,0].grid(True)
    axs[0,0].legend()
    # TODO: add diferent ylim for hpk and fbk types
    
    axs[0,1].axvline(x=Vbd_poly_trim*slope + intercept, color='purple' ,linestyle='dotted', label=r'$V_{bd}\ (trim)$' f'= {Vbd_poly_trim*slope + intercept:.1f}'  +r'$\pm$'+ f'{Vbd_error_poly_trim*slope + intercept:.1f} [V]') 
    axs[0,1].scatter(trim_volt,trim_curr, marker='o',s=5,color="orange", label='Trim')  
    if fit_bias:  
        axs[0,1].scatter(bias_v,bias_curr,marker='o',s=5, color="teal",label='Bias')
        try: 
            axs[0,1].axvline(x=Vbd_poly_bias*slope + intercept, color='purple' ,linestyle='--', label=r'$V_{bd}\ (bias)$' rf'= {Vbd_poly_bias*slope + intercept:.1f}' +r'$\pm$'+ f'{Vbd_error_poly_bias*slope + intercept:.1f} [V]') 
        except TypeError: pass
    axs[0,1].set_xlabel('Voltage [V]')
    axs[0,1].set_ylabel('Current [mA]')
    axs[0,1].set_title(f'REV IV - IP:{ip} APA: {apa} AFE: {afe} CH: {ch}')
    axs[0,1].legend()
    axs[0,1].grid(True)

    # axs[1,0].scatter(puls_filter_trim[0]*slope + intercept,puls_filter_trim[1],marker='o',s=5,color='orange', label = 'Der1_Sav1 PulseTrim')
    # axs[1,0].scatter(puls_2nd_trim[0]*slope + intercept,puls_2nd_trim[1],marker='^',s=5,color='salmon', label = 'Der1_Sav2 PulseTrim (Fit)')
    # if len(puls_filter_bias[0])!=1: axs[1,0].scatter(puls_filter_bias[0]*slope + intercept,puls_filter_bias[1],marker='o',s=5,color='teal',label = '1Der1_Sav1 PulseBias')
    # if len(puls_2nd_bias[0])!=1: axs[1,0].scatter(puls_2nd_bias[0]*slope + intercept,puls_2nd_bias[1],marker='^',s=5,color='cyan',label = 'Der1_Sav2 PulseBias (Fit)')
    # axs[1,0].axvline(x=Vbd_puls_trim*slope + intercept, color='purple' ,linestyle='dotted', label=r'$V_{bd}\ (trim)$' f'= {Vbd_puls_trim*slope + intercept:.1f}'  +r'$\pm$'+ f'{Vbd_error_puls_trim*slope + intercept:.1f} [V]') 
    # if not np.isnan(Vbd_puls_bias): axs[1,0].axvline(x=Vbd_poly_bias*slope + intercept, color='purple' ,linestyle='--', label=r'$V_{bd}\ (bias)$' rf'= {Vbd_puls_bias*slope + intercept:.1f}' +r'$\pm$'+ f'{Vbd_error_puls_bias*slope + intercept:.1f} [V]')
    # axs[1,0].set_xlabel('Voltage [V]')
    # axs[1,0].set_ylabel('Current [mA]')
    # axs[1,0].set_title(f'DER PULSESHAPE - IP:{ip} APA: {apa} AFE: {afe} CH: {ch}')
    # axs[1,0].legend()
    # axs[1,0].grid(True)

    axs[1,1].scatter(np.array(poly_filter_trim[0])*slope + intercept,poly_filter_trim[1],marker='s',s=5,color='red', label = 'Der1_Sav1 PolyTrim')
    axs[1,1].scatter(np.array(poly_2nd_trim[0])*slope + intercept,poly_2nd_trim[1],marker='^',s=5,color='salmon', label = 'Der1_Sav2 PolyTrim (Fit)')
    axs[1,1].axvline(x=Vbd_poly_trim*slope + intercept, color='purple' ,linestyle='dotted', label=r'$V_{bd}\ (trim)$' f'= {Vbd_poly_trim*slope + intercept:.1f}'  +r'$\pm$'+ f'{Vbd_error_poly_trim*slope + intercept:.1f} [V]') 
    if fit_bias:
        axs[1,1].scatter(np.array(poly_filter_bias[0])*slope + intercept,poly_filter_bias[1],marker='s',s=5,color='blue',label = 'Der1_Sav1 PolyBias')
        axs[1,1].scatter(np.array(poly_2nd_bias[0])*slope + intercept,poly_2nd_bias[1],marker='^',s=5,color='cyan',label = 'Der1_Sav2 PolyBias (Fit)')
        try: 
            axs[1,1].axvline(x=Vbd_poly_bias*slope + intercept, color='purple' ,linestyle='--', label=r'$V_{bd}\ (bias)$' rf'= {Vbd_poly_bias*slope + intercept:.1f}' +r'$\pm$'+ f'{Vbd_error_poly_bias*slope + intercept:.1f} [V]') 
        except TypeError: pass
    axs[1,1].set_xlabel('Voltage [V]')
    axs[1,1].set_ylabel('Current [mA]')
    axs[1,1].set_title(f'DER POLYNIMIAL - IP:{ip} APA: {apa} AFE: {afe} CH: {ch}')
    axs[1,1].legend()
    axs[1,1].grid(True)
    
    plt.tight_layout()
    pdf_pages.savefig(fig)
    plt.close(fig)