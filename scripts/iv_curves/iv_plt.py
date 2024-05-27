import os,click,uproot
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from scipy.signal import savgol_filter
from matplotlib.backends.backend_pdf import PdfPages
from rich.progress  import track
import warnings
warnings.filterwarnings("ignore")


def derivative(X, Y):
    dx = np.diff(X)
    dy = np.diff(Y)
    return dy/dx

@click.command()
@click.option("--dir", default = '/eos/experiment/neutplatform/protodune/experiments/ProtoDUNE-II/PDS_Commissioning/ivcurves/')
@click.option("--day", default = 'ALL')
def main(dir,day):
    '''
    This script generates a pdf with the results for IV curves.
    First subfigure represent Bias[V] vs Bias[DAC] to get the correction factor
     and the second shows the Current[A] vs Trim.

    Args:
        - dir (str): The directory where the root files are located. Default is '/eos/experiment/neutplatform/protodune/experiments/ProtoDUNE-II/PDS_Commissioning/ivcurves/'.
        - day (str): The day to look for the root files. If 'ALL' is selected, all the folders in the directory will be considered.
    Example: python iv_plt.py --dir /eos/experiment/neutplatform/protodune/experiments/ProtoDUNE-II/PDS_Commissioning/ivcurves/ --day Apr-01-2024-run00
    '''
    print(f'The selected directory to look for data folders is: {dir}')
    if day == "ALL": list_folders = os.listdir(f'{dir}')
    else: list_folders = [day]
    for folder in list_folders:
        if not os.path.isdir(f'{dir}{folder}') or "TMP" in folder:
            print('\033[91m'+'Not considering '+folder+'\033[0m') 
            continue
        else:
            print('\033[92m'+ 'Generating quality_checks.pdf in '+folder+ '\033[0m')
            pdf_pages = PdfPages(f'{dir}/{folder}/quality_checks.pdf')
            list_subfolders = [f for f in os.listdir(f'{dir}{folder}') if os.path.isdir(f'{dir}{folder}/{f}')]
            for subfolder in track(list_subfolders, description=f'Analysing {folder}...'):
                root_files = [f for f in os.listdir(f'{dir}{folder}/{subfolder}') if f.endswith('.root')]
                ip = subfolder.split("_")[-1].split(".")[-1]
                for r,root_file in enumerate(root_files):
                    plt_name = (root_file.split('/')[-1]).split('.')[0]
                    apa = (plt_name.replace('apa_','')).split('_')[0]
                    ch = int(plt_name.split('ch_')[-1])
                    afe =  ch//8

                    file = uproot.open(f'{dir}{folder}/{subfolder}/{root_file}')
                    bias_v = file['tree/bias/bias_v'].array(library="np")
                    bias_dac = file['tree/bias/bias_dac'].array(library="np")
                    trim = file['tree/iv_trim/trim'].array(library="np")
                    current = np.flip(file['tree/iv_trim/current'].array(library="np"))*(-1)

                    df = pd.DataFrame({'V':trim, 'I':current})
                    # for i in range(len(df) - 2):
                    #     if all(df.iloc[i:i+3]['I'] > 0):
                    #         df = df.iloc[i:]
                    #         break
                    savgol_window = (len(df['V'])) // 15  # 5 seems okay
                    df['I_savgol'] = savgol_filter(df['I'],savgol_window,1) 
                    df['der_norm'] = [i / j for i, j in zip(derivative(df['V'], df['I']), df['I'])] + [0] 
                    df['der_I_savgol'] = [i / j for i, j in zip(derivative(df['V'], df['I_savgol']), df['I_savgol'])] + [0] 
                    df['der_I_savgol_2'] = savgol_filter(df['der_I_savgol'],savgol_window*3,2)
                    peak_index= (df.iloc[7:-7]['der_I_savgol_2']).idxmax()

                    half_point_range = (len(df['V'])) // 12  # 6 seems okay
                    if half_point_range < 5: half_point_range = 5
                    min_index = peak_index - half_point_range
                    if min_index < 0: min_index = 0
                    max_index = peak_index + half_point_range 
                    if max_index < 0: max_index = len(df['V'])-1
                    df_fit = df.loc[min_index:max_index]

                    df_fit = df.loc[min_index:max_index]
                    poly2_coeff = np.polyfit(df_fit['V'], df_fit['der_I_savgol_2'], 2)
                    x_poly2 = np.linspace(df_fit.at[df_fit.index[0],'V'], df_fit.at[df_fit.index[-1],'V'], 100) 
                    y_poly2 = y_values = np.polyval(poly2_coeff, x_poly2)
                    Vbd = x_poly2[np.argmax(y_poly2)]

                    # Create a figure with all the subplots
                    fig, (ax1, ax2, ax3) = plt.subplots(1,3, figsize=(15,5))

                    ax1.scatter(bias_dac,bias_v)
                    ax1.set_title(f'CONVERSION - ENDPOINT:{ip} APA: {apa} AFE: {afe} CH: {ch}')
                    ax1.set_title(f'ip_{ip}_{root_file.replace(".root","")}')
                    ax1.set_xlabel('Bias DAC')
                    ax1.set_ylabel('Bias Voltage [V]')
                    ax1.grid(True)
                    # TODO: add diferent ylim for hpk and fbk types

                    # ax2.scatter(trim,current)
                    # ax2.set_title(f'ip_{ip}_{root_file.replace(".root","")}')
                    # ax2.set_xlabel('Trim')
                    # ax2.set_ylabel('Current [A]')
                    # # ax2.set_ylim((-10,230))
                    # ax2.grid(True)

                    ax2.scatter(df['V'], df['I'], marker='o',s=5, color='blue', label='Acquired')
                    ax2.scatter(df['V'], df['I_savgol'], marker='o',s=5, color='deepskyblue', label='Savgol')
                    ax2.set_xlabel('Trim Voltage [V]')
                    ax2.set_ylabel('Current [A]')
                    ax2.set_title(f'REV IV - ENDPOINT:{ip} APA: {apa} AFE: {afe} CH: {ch}')
                    ax2.grid(True)
                    ax2.legend()
                    
                    ax3.scatter(df["V"],df['der_norm'], marker='o', s=5, color='purple', label='dAcquired/dx')
                    ax3.scatter(df['V'],df['der_I_savgol'], marker='o', s=5, color='fuchsia', label='dSavgol/dx')
                    if df['der_I_savgol_2'].isna().all() : 
                        ax3.scatter(df["V"],df['der_I_savgol_2'], marker='o', s=5, color='orange', label='dAcquired/dx + Savgol')
                    ax3.scatter(df.loc[peak_index, 'V'],df.loc[peak_index, 'der_I_savgol_2'], marker='o', s=25, color='yellow', label='Maximum point')
                    ax3.plot(x_poly2, y_poly2, color='green', label = '2nd deg fit')
                    
                    ax3.axvline(x=Vbd, color='lime' ,linestyle='--', label=r'$V_{bd}$' f'= {Vbd:.0f} (DAC)')   

                    ax3.set_title(f'REV IV - ENDPOINT:{ip} APA: {apa} AFE: {afe} CH: {ch}')
                    ax3.set_xlabel('Bias Voltage [V]')
                    ax3.set_ylabel('Current [A]')
                    ax3.set_yscale('log')
                    ax3.grid(True)
                    ax3.legend()

                    plt.tight_layout()
                    pdf_pages.savefig(fig)

                    plt.close(fig)

        pdf_pages.close()

if __name__ == "__main__":
    main()