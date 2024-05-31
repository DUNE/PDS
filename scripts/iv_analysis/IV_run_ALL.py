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
            if datetime.strptime(((folder.split('/')[-1]).split('run')[0])[:-1], '%b-%d-%Y')>= datetime(2024, 4, 19):
                run_folders.append(folder)
    return run_folders
    

dir_list = get_directories('/eos/experiment/neutplatform/protodune/experiments/ProtoDUNE-II/PDS_Commissioning/ivcurves')


for input_dir in dir_list:
    subprocess.run([
        'python', 'IV_analysis.py',
        '--input_dir', input_dir,
        '--output_dir', getcwd() + '/../../data/iv_analysis',
        '--endpoint', '113',
        '--trimfit', 'poly',
        '--map_path', getcwd() + '/../../maps/original_channel_map.json'
    ])


