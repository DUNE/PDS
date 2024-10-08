'''
If you want to analyze all runs
'''

import subprocess
from pathlib import Path
from datetime import datetime
from os import getcwd

def get_directories(path):
    run_folders = []
    for folder in [str(d) for d in Path(path).iterdir() if d.is_dir()]:
        if ('run' in folder) and ('2024' in folder):
            run_string = (folder.split('/')[-1])
            data_string = (run_string.split('run')[0])[:-1]
            if datetime.strptime(data_string, '%b-%d-%Y') >= datetime(2024, 4, 19):
                run_folders.append(run_string)
    return run_folders

    

dir_list = get_directories('/eos/experiment/neutplatform/protodune/experiments/ProtoDUNE-II/PDS_Commissioning/ivcurves')

for run_i in dir_list:
    subprocess.run([
        'python', 'Vbd_determination.py',
        '--output_dir', '/afs/cern.ch/user/a/anbalbon/IV_curve/PDS/data/prova',
        '--run', run_i
    ])
