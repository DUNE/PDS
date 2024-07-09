'''
If you want to compute the breakdown of all runs
'''

import subprocess
from pathlib import Path
from datetime import datetime
from os import getcwd

def get_directories(path):
    run_folders = []
    for folder in [str(d) for d in Path(path).iterdir() if d.is_dir()]:
        if ('run' in folder) and ('2024' in folder):
            if datetime.strptime(((folder.split('/')[-1]).split('run')[0])[:-1], '%b-%d-%Y')>= datetime(2024, 4, 19):
                run_folders.append(folder)
    return run_folders


dir_list = get_directories('/eos/experiment/neutplatform/protodune/experiments/ProtoDUNE-II/PDS_Commissioning/ivcurves')


for dir in dir_list:
    print(f"\n############################## {dir.split('/')[-1]} ##############################\n")
    subprocess.run([
        'python', 'Vbd_determination.py',
        '--input_dir', dir,
        '--output_dir', getcwd() + '/../../data/iv_analysis_prova'
    ])

