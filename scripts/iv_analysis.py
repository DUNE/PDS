import click, json
import numpy as np
from os import chdir, listdir
from uproot import open as op
from scipy.optimize import curve_fit
from scipy.signal import savgol_filter

map = {
    '10.73.137.104': {'apa': 1, 'fbk': [0, 1, 2, 3, 4, 5, 6, 7], 'hpk': [8, 9, 10, 11, 12, 13, 14, 15], 'fbk_value': 1060, 'hpk_value': 1560},
    '10.73.137.105': {'apa': 1, 'fbk': [0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 13, 15], 'hpk': [17, 19, 20, 22], 'fbk_value': 1090, 'hpk_value': 1480},
    '10.73.137.107': {'apa': 1, 'fbk': [0, 2, 5, 7], 'hpk': [8, 10, 13, 15], 'fbk_value': 1090, 'hpk_value': 1575},
    '10.73.137.109': {'apa': 2, 'fbk': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15], 'hpk': [16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39], 'fbk_value': 1090, 'hpk_value': 1585},
    '10.73.137.111': {'apa': 3, 'fbk': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23], 'hpk': [24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39], 'fbk_value': 1085, 'hpk_value': 1590},
    '10.73.137.112': {'apa': 4, 'fbk': [], 'hpk': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 34, 37, 39], 'fbk_value': 0, 'hpk_value': 1580},
    '10.73.137.113': {'apa': 4, 'fbk': [0, 2, 5, 7], 'hpk': [], 'fbk_value': 1040, 'hpk_value': 0},
}


def data_quality(data):
    '''
    Check the quality of the data set. Errors are returned if the sample:
        - is smaller than 20,
        - all the current values are NaN
        - more than 10 NaN values are present
        - all the current values are negative
        - all the current values are below 50
        - the current range is less than 100 [CHECKING THIS ONE]
    '''
    if len(data) < 20:
        return ['BAD', 'ERROR: Less than 20 samples !!!']
    if np.count_nonzero(np.isnan(data)) == len(data):
        return ['BAD', 'ERROR: All current info is NaN !!!']
    elif (np.count_nonzero(np.isnan(data)) >= 10):
        return ['BAD', 'ERROR: More than 10 NaN values for current !!!']
    elif (np.count_nonzero(np.isnan(data)) > 0) and (np.count_nonzero(np.isnan(data)) < 10):
        return ['OK', 'Warning: some NaN value for current, less than 10 NaN!']

    if (data < 0).sum() == len(data):
        return ['BAD', 'ERROR: Negative current !!!']
    if (data < 50).sum() == len(data):
        return ['BAD', 'ERROR: Current is too low !!!']
    if data[len(data)-1]-data[0] < 100:
        return ['BAD', 'ERROR: Wrong current range, check the voltage range !!!']

    return ['OK', 'Good data set!']


def fit_pulse(t, t0, T, A, P):
    '''
    Fit function for the pulse shape
    '''
    x = (np.array(t) - t0+T)/T
    return P+A*np.power(x, 3)*np.exp(3*(1-x))


def IV_PulseShape(bias, der_current,  savgol_window):
    '''
    Fit the pulse shape of the IV curve
    '''

    b = bias/100
    # Filter with n=2, just to remove some noise
    n = 2
    print(len(der_current) % 2)
    y = savgol_filter(der_current, n, 1)

    # The breakdown voltage seems to be always after the second half of the plot
    n_cut = 10  # int(len(b)/2)
    peak = savgol_filter(y, 3 * savgol_window, 2)[n_cut:]
    # 3 is an arbitrary constant that can be changed according with the amount of data
    index = (np.argmax(peak) + n_cut) - 3

    # Choosing boundaries values for the fitting
    delta = len(b) - index
    if delta >= 5 and index >= 5:
        min_guess = b[index-5]
        max_guess = b[len(b)-1]
    if delta < 5 and index >= 5:
        min_guess = b[index - int(delta/2)]
        max_guess = b[index + int(delta/2)]
    if index <= 5:
        min_guess = b[0]
        max_guess = b[index + 5]

    # Fit using a pulse shape function
    x_bias = np.arange(min_guess, b[len(b)-1], 0.01)
    try:
        popt, pcov = curve_fit(fit_pulse, b[index:], y[index:], bounds=(
            [min_guess, 0, 0, -0.5], [max_guess, 100, 100, 0.5]))
        y_fit = fit_pulse(x_bias, popt[0], popt[1], popt[2], popt[3])
        if len(y_fit) > 1:

            breakdown = x_bias[np.argmax(y_fit)]

            if breakdown*100 < 2400:
                return [breakdown*100, x_bias*100, y_fit]
            else:
                return [0, 0, 0]

        else:
            return [0, 0, 0]
    except:
        return [0, 0, 0]


def IV_Polynomial(bias, der_current, step, savgol_window):
    '''
    Fit the polynomial of the IV curve (Savgol method)
    '''

    # Second filter
    c = savgol_filter(der_current, savgol_window*3, 2)
    if np.count_nonzero(np.isnan(c)) == len(c):
        return [0, 0, 0]

    # Search for the maximum of first derivative (filtered)
    peak_index = np.argmax(c)

    # Select few points around the peak
    # half_point_range = (len(df['V'])) // 12  # 6 seems okay
    if (step > 40):
        half_point_range = 6  # 5 seems okay -> it depends on the step
    elif (step <= 40) and (step > 10):
        half_point_range = 8
    else:
        half_point_range = 10

    min_index = peak_index - half_point_range
    if min_index < 0:
        min_index = 0
    max_index = peak_index + half_point_range
    if max_index < 0:
        max_index = len(bias)-1

    # Parabolic fit
    try:
        poly2_coeff = np.polyfit(
            bias[min_index:max_index], c[min_index:max_index], 2)
        x_poly2 = np.linspace(bias[min_index], bias[max_index], 100)
    except:
        poly2_coeff = np.polyfit(
            bias[min_index:len(bias)-1], c[min_index:len(c)-1], 2)
        x_poly2 = np.linspace(bias[min_index], bias[len(bias)-1], 100)
    y_poly2 = np.polyval(poly2_coeff, x_poly2)

    if (poly2_coeff[0] > 0):
        return [0, 0, 0]
    else:
        breakdown = x_poly2[np.argmax(y_poly2)]
        return [breakdown, x_poly2, y_poly2]


@click.command()
@click.option("--dir", default='/eos/experiment/neutplatform/protodune/experiments/ProtoDUNE-II/PDS_Commissioning/ivcurves/Mar-21-2024-run00')
def main(dir):
    chdir(dir)
    # Output File
    output_file = open(f"{dir}/breakdown_output.txt", 'w')
    output_file.write(
        f"IP\tFile\tSIPM\tStatus\tVbd(Suggested)\tVdbd(Pulse)\tVbd(Poly)\n")

    folders = sorted(listdir())
    for i in range(len(folders)):
        if len(folders[i]) > 40:

            chdir(f"{dir}/{str(folders[i])}")
            files = sorted(listdir())
            run = f"{(folders[i].split('/')[-1]).split('_')[0]}_{(folders[i].split('/')[-1]).split('_')[1]}"

            ip_address = (folders[i].split('/')[-1]).split('ip')[-1]
            dic = map[ip_address]
            fbk = map[ip_address]['fbk']
            hpk = map[ip_address]['hpk']

            conversion_list = [[], [], [], [], []]
            sipm_afe = [[], [], [], [], []]
            channel_afe = [[], [], [], [], []]

            # To control bias/trim per afe
            bias_AFE = [[], [], [], [], []]
            trim_AFE = [[], [], [], [], []]

            for j in range(len(files)):
                if files[j][len(files[j])-4:] == 'root':
                    # AFE
                    afe = int(files[j][10])

                    # Checking channel and associated sipm
                    if len(files[j]) == 21:
                        channel = int(files[j][15])
                    else:
                        channel = int(files[j][15:17])
                    if channel in fbk:
                        sipm = 'FBK'
                    else:
                        sipm = 'HPK'
                    sipm_afe[afe].append(sipm)

                    root_file = op(files[j])
                    # DAC -> Bias relation and overvoltage calculation
                    dac = root_file["tree/bias/bias_dac"].array()
                    bias = root_file["tree/bias/bias_v"].array()
                    DAC_BIAS = np.polyfit(bias, dac, 1)
                    conversion_list[afe].append([DAC_BIAS[0], DAC_BIAS[1]])
                    print(f'AFE: {afe}')
                    print(f'CONVERSION FACTOR: {conversion_list[afe]}') ## slope and intercept values

                    # Breakdown via trim
                    current = (root_file["tree/iv_trim/current"].array())[::-1]
                    trim = root_file["tree/iv_trim/trim"].array()
                    quality = data_quality(np.array(current))

                    if quality[0] == 'BAD':
                        Vbd_trim = Vbd_pulse = Vbd_poly = 0
                        status = quality[1]

                    else:
                        # Removing negative currents
                        t = []
                        c = []
                        for k in range(len(current)):
                            if current[k] > 0:
                                c.append(current[k])
                                t.append(trim[k])
                        c = np.array(c)
                        t = np.array(t)

                        # First filter
                        step = round(np.mean(np.diff(t)))
                        if (step > 40):
                            savgol_window = 4  # 5 seems okay -> it depends on the step
                        elif (step <= 40) and (step > 10):
                            savgol_window = 5
                        else:
                            savgol_window = 7
                        current_filtered = savgol_filter(c, savgol_window, 1)

                        # relative derivative
                        der_current = np.nan_to_num(np.gradient(
                            current_filtered)/current_filtered)

                        PulseShape = IV_PulseShape(
                            t, der_current, savgol_window)
                        Polynomial = IV_Polynomial(
                            t, der_current, step, savgol_window)

                        Vbd_pulse = float(PulseShape[0])
                        Vbd_poly = float(Polynomial[0])
                        Delta = abs(Vbd_pulse - Vbd_poly)

                        if Vbd_pulse != 0 and Vbd_poly != 0 and Delta < 200:
                            # We can change it depending on the performance comparison
                            Vbd_trim = int((Vbd_pulse + Vbd_poly)/2)
                            status = "Good data set"
                        elif Vbd_pulse != 0 and Vbd_poly != 0 and Delta >= 200:
                            Vbd_trim = Vbd_pulse = Vbd_poly = 0
                            status = f"ERROR: The Difference between the Vbd_poly and Vbd_pulse is too large ({Delta}). "
                        elif Vbd_pulse == 0 and Vbd_poly != 0:
                            Vbd_trim = int(Vbd_poly)
                            status = "WARNING: the pulse shape fitting method failled, please check the plots. "
                        elif Vbd_pulse != 0 and Vbd_poly == 0:
                            Vbd_trim = int(Vbd_pulse)
                            status = "WARNING: the polynomial fitting method failled, please check the plots. "
                        else:
                            Vbd_trim = Vbd_pulse = Vbd_poly = 0
                            status = "ERROR: Both fitting methods failed. "

                    channel_afe[afe].append(channel)
                    bias_AFE[afe].append(int(dac[len(dac)-1]))
                    trim_AFE[afe].append(Vbd_trim)

                    print(
                        f" {ip_address} file:{files[j]} SiPM: {sipm} Status: {status} Vbd_TRIM(DAC) = {Vbd_trim}")
                    output_file.write(
                        f"{ip_address}\t{files[j]}\t{sipm}\t{status}\t{Vbd_trim}\t{Vbd_pulse}\t{Vbd_poly} \n")

            conversion_list_mean = []
            for vector in range(len(conversion_list)):
                sum_a = sum_b = quantity = 0
                if len(conversion_list[vector]) > 0:
                    for vector2 in range(len(conversion_list[vector])):
                        a = conversion_list[vector][vector2][0]
                        b = conversion_list[vector][vector2][1]
                        if a > 0:
                            sum_a += a
                            sum_b += b
                            quantity += 1
                    conversion_list_mean.append(
                        [sum_a/quantity, sum_b/quantity])

            bias_AFE_mean = []
            bias_AEF_dif = []
            overvoltage_list = []
            trim_AFE_dif = [[], [], [], [], []]
            trim_final_list = []
            for vector in range(len(bias_AFE)):
                if len(bias_AFE[vector]) > 0:
                    bias_AFE_mean.append(np.mean(bias_AFE[vector]))
                    sipm = sipm_afe[vector][0]

                    overvoltage_results = []
                    result_afe = []

                    for vector2 in range(len(bias_AFE[vector])):
                        dif = np.mean(bias_AFE[vector]) - \
                            np.array(bias_AFE[vector][vector2])
                        bias_AEF_dif.append(dif)
                        if conversion_list[vector][vector2][0] < 0:
                            a = conversion_list_mean[vector][vector2][0]
                            b = conversion_list_mean[vector][vector2][0]
                        else:
                            a = conversion_list[vector][vector2][0]
                            b = conversion_list[vector][vector2][1]

                        dif_volt = (dif - b)/a  # convert DAC_bias in volt
                        dif_trim = dif_volt/0.001  # convert Volt to DAC
                        trim_AFE_dif[vector].append(dif_trim)

                        if sipm == 'FBK':
                            overvoltage = a*(4.5)+b
                        else:
                            overvoltage = a * 3.5 + b
                        overvoltage_results.append(overvoltage)

                        if trim_AFE[vector][vector2] == 0:
                            result_afe.append(0)
                        else:
                            result_afe.append(
                                trim_AFE[vector][vector2] - trim_AFE_dif[vector][vector2])

                    overvoltage_list.append(np.mean(overvoltage_results))
                    trim_final_list.append(result_afe)

            channel_list = []
            trim_channel = []
            for vector in range(len(trim_final_list)):
                channel_list += channel_afe[vector]
                trim_channel += trim_final_list[vector]
            del channel_afe, trim_final_list

            Trim_FBK = np.zeros(len(fbk))
            for ch in fbk:
                index_fbk = fbk.index(ch)
                if ch in channel_list:
                    index = channel_list.index(ch)
                    Trim_FBK[index_fbk] = trim_channel[index]

            Trim_HPK = np.zeros(len(hpk))
            for ch in hpk:
                index_hpk = hpk.index(ch)
                if ch in channel_list:
                    index = channel_list.index(ch)
                    Trim_HPK[index_hpk] = trim_channel[index]

            dic["Vbd_per_AFE"] = bias_AFE_mean
            dic["Overvoltage"] = overvoltage_list

            dic["FBK_Vbd_trim"] = np.ndarray.tolist(Trim_FBK)
            dic["HPK_Vbd_trim"] = np.ndarray.tolist(Trim_HPK)

            dic['run'] = run

            with open(f"{dir}/{ip_address}_map.json", "w") as fp:
                json.dump(dic, fp)

    output_file.close()


if __name__ == "__main__":
    main()
