'''
IV analysis utilis

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
import sys
#warnings.filterwarnings("ignore", category=OptimizeWarning)




#Original map
original_map  = {
    '10.73.137.104': {'apa': 1, 'fbk': [0, 1, 2, 3, 4, 5, 6, 7], 'hpk': [8, 9, 10, 11, 12, 13, 14, 15]},
    '10.73.137.105': {'apa': 1, 'fbk': [0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 13, 15], 'hpk': [17, 19, 20, 22]},
    '10.73.137.107': {'apa': 1, 'fbk': [0, 2, 5, 7], 'hpk': [8, 10, 13, 15]},
    '10.73.137.109': {'apa': 2, 'fbk': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15], 'hpk': [16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39]},
    '10.73.137.111': {'apa': 3, 'fbk': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23], 'hpk': [24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39]},
    '10.73.137.112': {'apa': 4, 'fbk': [], 'hpk': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 34, 37, 39]},
    '10.73.137.113': {'apa': 4, 'fbk': [0, 2, 5, 7], 'hpk': []},
}



# New map from 24/09/2024
map_mod_20240924= {
    '10.73.137.104': {'apa': 1, 'fbk': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23], 'hpk': [24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39]},
    '10.73.137.109': {'apa': 2, 'fbk': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15], 'hpk': [16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39]},
    '10.73.137.111': {'apa': 3, 'fbk': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23], 'hpk': [24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39]},
    '10.73.137.112': {'apa': 4, 'fbk': [], 'hpk': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 34, 37, 39]},
    '10.73.137.113': {'apa': 4, 'fbk': [0, 2, 5, 7], 'hpk': []},
}



def derivative(y):
    return np.nan_to_num(np.gradient(y)/y) 

def derivative_anna(x, y):
    dx = np.diff(x)
    dy = np.diff(y)
    return np.append(dy/dx,0) #/y

def derivative_cactus(x,y):
    return -np.gradient(np.log(y), x)
    
def linear_function(x, m, b):
    return m * x + b

def parabolic_function(x,a,b,c):
    return a*x*x + b*x + c

def bias_data_quality(current):
    if len(current) <10:
        return 'BAD(less than 10 samples)'
    elif (np.count_nonzero(np.isnan(current)) >= 10):
        return 'BAD(more than 10 NaN currents)'

    #NEW ANNA
    if (current[-1]< np.mean(current[:10])+0.02) and (current[-2]< np.mean(current[:10]+0.02)):
        return 'BAD(dead channel or wrong bias range)'
    '''
    #OLD
    if (max(current) - min(current)) < 0.05 : 
        return 'BAD(check bias current)'
    '''
    return 'Good'

def trim_data_quality(current):
    '''
    Check the quality of the data set. Errors are returned if:
        - the trim sample is smaller than 20,
        - all there are more than 10 NaN values 
        - the current range is lower than 0.2

    It returns a string:
        - Good if data are okay and we can procede with the analysis
        - Error / Warning associated to the data acquired
    '''

    if len(current) < 20:
        return 'BAD(less than 20 samples)'
    if np.count_nonzero(np.isnan(current)) == len(current):
        return 'BAD(all currents are NaN)'
    elif (np.count_nonzero(np.isnan(current)) >= 10):
        return 'BAD(more than 10 NaN currents)'
    elif (np.count_nonzero(np.isnan(current)) > 0) and (np.count_nonzero(np.isnan(data)) < 10):
        return 'Good(Warning: some NaN value for current)' 

    if (max(current)-min(current)) < 0.10:
        return 'BAD(check trim current)'
    
    return 'Good'


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
    y = savgol_filter(der, sgf[0], sgf[1])
    if np.count_nonzero(np.isnan(y)) == len(y):
        return [np.nan, np.nan, [0, 0], [0,0], sgf]

    #Search for the maximum of first filtered derivative
    peak_index = np.argmax(y[10:-10])+10

    #Select few points around the peak (more than 5 is ok)
    half_point_range = 8

    min_index = peak_index - half_point_range
    if min_index < 0:
        min_index = 0
    max_index = peak_index + half_point_range
    if max_index > len(x)-1:
        max_index = len(x)-1

    #Parabolic fit
    #poly2_coeff = np.polyfit(x[min_index:max_index], y[min_index:max_index], 2)
    poly2_coeff, poly2_cov = curve_fit(parabolic_function, x[min_index:max_index], y[min_index:max_index])
    poly2_errors = np.sqrt(np.diag(poly2_cov))
    
    x_poly2 = np.linspace(x[min_index], x[max_index], 100)
    y_poly2 = np.polyval(poly2_coeff, x_poly2)

    if (poly2_coeff[0] > 0): #Check if it has the correct concavity 
        return [np.nan, np.nan, [0,0], [0,0], sgf]
    else:
        #Vbd = x_poly2[np.argmax(y_poly2)]
        Vbd = -poly2_coeff[1] / (2*poly2_coeff[0])
        if (Vbd < x[5]) or (Vbd > x[len(x)-5]): #Check if Vbd is not on the first or last points 
            return [np.nan, np.nan, [0,0], [0,0], sgf]
        else:
            Vbd_error = np.sqrt((poly2_errors[1]/(2*poly2_coeff[0]))**2 + (poly2_coeff[1]*poly2_errors[0]/(2*poly2_coeff[0]*poly2_coeff[0]))**2)
            return [Vbd, Vbd_error, [x, y], [x_poly2, y_poly2], sgf]
        


def fit_pulse(t, t0, T, A, P):
    x = (np.array(t) - t0+T)/T
    return P+A*np.power(x, 3)*np.exp(3*(1-x))


def IV_PulseShape(trim, der, step, sgf):
    '''
    Pulse Shape fit of the trim IV curve
    It returns an array of three element:
    -  Vbd trim from IV curve fit 
    -  An array with trim and filtered derivative used for the fit
    -  An array with x and y  coordinante to reconstruct the fitting function 
    -  An array with information of the savgol filter (window and degree)
    '''

    #Savgol filter on 1st normalized derivative
    x = trim/100
    y = savgol_filter(der, sgf[0], sgf[1])

    #Search for the peak
    n_cut = 10 # Vbd seems to be always after the second half of the plot
    peak = savgol_filter(y, 20, 2)[n_cut:]
    index = (np.argmax(peak) + n_cut) - 3 # 3is an arbitrary constant that can be changed according with the amount of data
    
    #Choosing boundaries values for the fitting
    delta = len(x) - index
    if delta >= 5 and index >= 5:
        min_guess = x[index-5]
        max_guess = x[len(x)-1]
    if delta < 5 and index >= 5:
        min_guess = x[index - int(delta/2)]
        max_guess = x[index + int(delta/2)]
    if index <= 5:
        min_guess = x[0]
        max_guess = x[index + 5]

    #Fit using a pulse shape function
    x_pulse = np.arange(x[np.where(x == min_guess)[0][0]+4], x[(index+25)], 0.01)
    try:
        popt, pcov = curve_fit(fit_pulse, x[index:], y[index:], bounds=([min_guess, 0, 0, -0.5], [max_guess, 100, 100, 0.5]))
        y_pulse = fit_pulse(x_pulse, popt[0], popt[1], popt[2], popt[3])

        if (len(y_pulse) < 2) or (y_pulse[0]==y_pulse.max()) or (y_pulse[-1]==y_pulse.max()) or (np.max(y_pulse) > 5*np.max(y[index:])):
            return [np.nan, np.nan, [0, 0], [0, 0], sgf]
        else:
            #Vbd = x_pulse[np.argmax(y_pulse)] *100
            Vbd = popt[0]*100
            Vbd_error = (np.sqrt(np.diag(pcov))[0])*100

            if (Vbd > 100) and (Vbd < x.max()*100-100):
                return [Vbd, Vbd_error, [x*100, y], [x_pulse*100, y_pulse], sgf]
            else:
                return [np.nan, np.nan, [0, 0], [0, 0], sgf]
    except:
        return [np.nan, np.nan, [0, 0], [0, 0], sgf]


     
    
def plot_trim_2(ax, trim_status, trim, current, c_filtered, Polynomial, PulseShape):
    '''  To create the plot of the Trim IV curve, with fit results (if fit works) '''
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
        ax_twin.legend(loc='upper right',fontsize='5')
        
    ax.legend(loc='center right',fontsize='5')
    ax.set_title('Trim REV IV curve')


def plot_bias_2(ax, bias, current):
    '''  To create the plot of the Bias IV curve - version 2 '''
    Vbd_bias = bias[-1]
    ax.set_xlabel("Bias (DAC)")
    ax.set_ylabel("Current") #Unit of measure(?)
    #ax.set_yscale('log')
    ax.scatter(bias, current, marker='o',s=5, color='blue', label='Acquired Bias IV curve')
    ax.axvline(x=Vbd_bias, color='red' ,linestyle='--', label= r'Bias $V_{bd}$* = '+f'{Vbd_bias:.0f} (DAC)')
    ax.legend(loc='center left',fontsize='7')
    ax.set_title('Bias REV IV curve')

    der =  derivative_anna(bias, current)
    ax_twin = ax.twinx()
    ax_twin.set_ylabel('Normalized Derivative')
    ax_twin.scatter(bias,der, marker='o', s=5, color='orange', label='First normalized derivative') 
    #ax_twin.legend(loc='upper left',fontsize='7')
    

def plot_bias_trim_2(ax, bias, current_bias, bias_conversion, trim, current_trim):
    ''' To create the plot of the whole IV curve (trim and bias) in terms of volt '''
    bias_v = bias_conversion[0] * np.array(bias) + bias_conversion[1] 
    trim_v = bias_v[-1] - np.array(trim) * (4.4 / 4095.0)
    ax.set_xlabel("Volt")
    ax.set_ylabel("Current") #Unit of measure(?)
    ax.scatter(bias_v, current_bias, marker='o', s=5, color='blue', label='Acquired Bias IV curve')
    ax.scatter(trim_v, current_trim, marker='o', s=5, color='red', label='Acquired Trim IV curve')
    ax.legend(loc='center left', fontsize='7')
    ax.set_title('Bias + Trim REV IV curve')

def plot_bias_conversion_2(ax,bias_dac,bias_V,bias_conversion):
    ax.set_xlabel("Volt")
    ax.set_ylabel("DAC") #Unit of measure(?)
    ax.scatter(bias_dac, bias_V, marker='o', s=7, color='blue', label='Acquired data')
    x = np.linspace(bias_dac[0], bias_dac[-1], 10)
    y = bias_conversion[0]*x+bias_conversion[1]
    ax.plot(x, y, color='red', label=f'Linear fit\ny={bias_conversion[0]:.3f}x+{bias_conversion[1]:.3f}')
    ax.legend(loc='upper left', fontsize='7')
    ax.set_title('Bias DAC-VOLT conversion')
    
    
def plot_IVbias_AFE(pdf_file_bias_AFE,endpoint,apa,sipm_AFE,bias_dac_AFE, current_bias_AFE, Vbd_bias_dac_AFE, channel_AFE):
    '''   To create the plot of Bias IV curve for each AFE '''
    for afe in range(5):
        if len(channel_AFE[afe]) != 0:
            fig, ax = plt.subplots(figsize=(8,6))
            fig.suptitle(f'REV Bias IV curve \n ENDPOINT:{endpoint} APA:{apa:.0f} SiPM:{sipm_AFE[afe][0]} AFE:{afe:.0f}')
            ax.set_xlabel("Bias (DAC)")
            ax.set_ylabel("Current")
            color_list = ['red','blue','green','purple','orange','grey','aqua','violet']
            for i in range(len(bias_dac_AFE[afe])):
                if len(bias_dac_AFE[afe][i]) > 0:
                    ax.scatter(bias_dac_AFE[afe][i], current_bias_AFE[afe][i], marker='o',s=5, color=color_list[i], label=f'Channel: {channel_AFE[afe][i]:.0f}')
            ax.legend(loc='center left',fontsize='7')
            plt.tight_layout()
            pdf_file_bias_AFE.savefig(fig)
            plt.close(fig)

def plot_production(pdf_file_NEW,endpoint,apa,afe,ch,sipm,bias_status,bias_dac,bias_V,bias_c,DAC_V_bias_conversion,trim_dac,trim_c,trim_status,c_filtered,Polynomial,PulseShape):
    fig, axs = plt.subplots(2, 2, figsize=(10, 8))
    if bias_status is None: 
        fig.suptitle(f'ENDPOINT:{endpoint} APA:{apa:.0f} AFE:{afe:.0f} Config_CH:{ch:.0f} CH_daq:{daq_channel_conversion(ch):.0f} SiPM:{sipm} --> MISSING FILE')
    else:
        fig.suptitle(f'ENDPOINT:{endpoint} APA:{apa:.0f} AFE:{afe:.0f} Config_CH:{ch:.0f} DAQ_CH:{daq_channel_conversion(ch):.0f} SiPM:{sipm}')  
        plot_bias_2(axs[0, 0],bias_dac, bias_c)
        if bias_status == 'Good':
            plot_bias_conversion_2(axs[0, 1], bias_dac, bias_V,DAC_V_bias_conversion)
            plot_bias_trim_2(axs[1, 0], bias_dac, bias_c, DAC_V_bias_conversion, trim_dac,  trim_c)
            plot_trim_2(axs[1, 1], trim_status, trim_dac, trim_c, c_filtered, Polynomial, PulseShape)
            if 'Good' not in trim_status:
                axs[1, 1].text(axs[1, 1].get_xlim()[-1]*0.6,axs[1, 1].get_ylim()[-1]*0.8,'Trim scan error',bbox={'facecolor': 'red', 'alpha': 0.5, 'pad': 10})
        else:
            axs[0, 0].text(axs[0, 0].get_xlim()[0]*1.04,axs[0, 0].get_ylim()[-1]*0.8,'Bias scan error',bbox={'facecolor': 'red', 'alpha': 0.5, 'pad': 10})
            
    plt.tight_layout()
    pdf_file_NEW.savefig(fig)
    plt.close(fig)
    

def DAC_VOLT_bias_conversion(bias_dac, bias_conversion):
    '''  Bias conversion: from DAC to VOLT '''
    if np.isnan(bias_dac):
        return np.nan
    else:
        return bias_conversion[0]*bias_dac + bias_conversion[1]

def DAC_VOLT_trim_conversion(trim_dac):
    '''  Trim conversion: from DAC to VOLT '''
    if np.isnan(trim_dac):
        return np.nan
    else:
        return trim_dac * (4.4/4095.0)

def DAC_VOLT_full_conversion (bias_dac, trim_dac, bias_conversion):
    '''  To obtain VOLTS from TRIM and BIAS in DAC'''
    if np.isnan(bias_dac) or np.isnan(trim_dac):
        return np.nan
    else:
        return DAC_VOLT_bias_conversion(bias_dac,bias_conversion) - DAC_VOLT_trim_conversion(trim_dac)

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

def daq_channel_conversion(ch_config):
    afe = int(ch_config//8)
    return 10*(afe) + (ch_config - afe*8)


def endpoint_list_data(folder_name):
    new_conf_data = datetime(2024, 9, 24)
    if 'run' in folder_name:
        string_data = datetime.strptime(folder_name.split('-run')[0], '%b-%d-%Y')
    elif 'Vbd_best_' in folder_name:
        string_data = datetime.strptime(folder_name.split('Vbd_best_')[-1], '%Y%m%d')
    elif 'Vbd_LN2T_' in folder_name:
        string_data = datetime.strptime("Oct-21-2024", "%b-%d-%Y")
    else:
        sys.exit('Error: not valid folder name!') 
        
    if string_data >= new_conf_data:
        endpoint_list = ['104','109', '111', '112', '113']
        map_to_use = map_mod_20240924
    else:
        endpoint_list = ['104', '105', '107', '109', '111', '112', '113']
        map_to_use = original_map
    return map_to_use