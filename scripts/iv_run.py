# RUN: python3 iv_run.py --in_dir "/eos/experiment/neutplatform/protodune/experiments/ProtoDUNE-II/PDS_Commissioning/"

import os,click,warnings
import pandas as pd
warnings.filterwarnings("ignore", category=FutureWarning)

@click.command()
@click.option("--in_dir",  default = '/eos/experiment/neutplatform/protodune/experiments/ProtoDUNE-II/PDS_Commissioning/ivcurves/', help='Input directory to look for data folders. Default: /eos/experiment/neutplatform/protodune/experiments/ProtoDUNE-II/PDS_Commissioning/ivcurves/')
@click.option("--out_dir", default = 'SAME', help='Output directory to save the summary file. Default: SAME')
@click.option("--force",   default = False,  help='Force the analysis of all folders, even if they have been already analysed. Default:False')
def iv_run(in_dir,out_dir,force):
    '''
    This script is used to collect the output of the ivcurves and/or analyse again all of them.
    Args:
        - in_dir: Input directory to look for data folders. Default: /eos/experiment/neutplatform/protodune/experiments/ProtoDUNE-II/PDS_Commissioning/ivcurves/
        - out_dir: Output directory to save the summary file. Default: SAME
        - force: Force the analysis of all folders, even if they have been already analysed. Default:False
    '''

    print(f'\033[36m\n[INFO] The selected directory to look for data folders is: {in_dir} \nTo change it run: python all_ivcurves.py --in_dir "/your/path/with/folders/"\n \033[0m')
    list_folders = [folder for folder in os.listdir(f'{in_dir}') if os.path.isdir(f'{in_dir}{folder}')]
    if out_dir == 'SAME': out_dir = in_dir        # If no output directory is given, the output will be saved in the same directory
    output_file = f'{out_dir}all_fits_output.txt' # Output file with all the data
    for folder in list_folders: # Loop over all folders inside the input directory
        if not bool(force):     # If force is not activated, check if the folder has been already analysed
            try: 
                df_saved = pd.read_csv(output_file,sep='\t',header=0)   # Read the output file
                all_data = df_saved                                     # If the file exists, append the new data to the existing one
                if folder in list(set(df_saved["Folder"].values)):      # Check if the folder has been already analysed
                    print('\033[35m'+ 'Already analysed '+folder+ '\033[0m')
                    continue # If the folder has been already analysed, skip it
            except FileNotFoundError: 
                all_data = pd.DataFrame() # If the file does not exist, create a new one
                print('\033[91m'+'No summary output file found, analysing ALL folders'+'\033[0m')
        else: all_data = pd.DataFrame()   # If force is activated, analyse all folders and replace the outputs

        print('\033[92m'+ '\nNew! Analysing '+folder+ '\033[0m')
        os.system(f'python iv_ana.py --in_dir {in_dir}{folder}') # Execute IV_Analyses for each folder
        list_files = os.listdir(f'{in_dir}{folder}')             # List all files in the folder
        if f"{folder}_fit.txt" in list_files:                    # Check if the output file is in the folder
            print(f'\033[36mFile {folder}_fits.txt generated! --> extracting the data... \033[0m')
            df = pd.read_csv(f'{in_dir}{folder}/{folder}_fit.txt',sep='\t',header=None) # Read the output file
            df = df.drop(df.index[0]) # Drop the first row to personalize the columns
            df.columns = [f"IP", "File", "APA", "AFE", "CH", "SIPM", "Slope[V/DAC]", "Intercept[V]", "Vbd(Suggested)", "Vbd(Pulse)", "Vbd(Poly)", "Status"]
            df['Folder'] = folder # Add the folder name to the dataframe
            all_data = pd.concat([all_data,df], ignore_index=True)  # Append df to all_data
        else:  # If the output file is not in the folder, print a warning
            print('\033[91m'+'Not output txt file'+'\033[0m') 
            continue
        all_data.to_csv(output_file, sep='\t', index=False) # Save the output file


if __name__ == "__main__": iv_run()