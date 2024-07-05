'''
Create the full map with ID, CH, bias and trim of Voperation, overvoltage and run for che configuration 

'''

import click
import json
import numpy as np
from os import chdir, listdir, path, makedirs, getcwd

@click.command()
@click.option("--run", 
              default='Jun-18-2024-run00',
              help="Run you want to study, like Jun-18-2024-run00 (default: 'Jun-18-2024-run00'") 
@click.option("--input_dir", 
              default=getcwd() + '/../../data/iv_analysis',
              help="Folder with results of the IV analysis' ") 
@click.option("--input-json-name", 
              default='dic' , 
              help="Name of the json file you want to read (produced by IV_analysis.py, default: 'dic')")
@click.option("--output_dir", 
              default= getcwd() + '/../../data/iv_analysis/',
              help="Path of the directory where to save the new compelte map (default: 'PDS/data/iv_analysis')")
@click.option("--output-json-name", 
              default=None , 
              help="Name for the json file with complete information (default: 'complete_dic_FBK(x,xV)_HPK(y,yV)')")

def main(run, input_dir, input_json_name, output_dir, output_json_name):
    map_complete = {'10.73.137.104':{},'10.73.137.105':{},'10.73.137.107':{},'10.73.137.109':{},'10.73.137.111':{},'10.73.137.112':{},'10.73.137.113':{}}
    chdir(input_dir+'/'+run)
    for folder in listdir():
        if any(folder.endswith(ip) for ip in list(map_complete.keys())):
            ip = folder.split('ip')[-1]
            id = int(folder.split('.')[-1][-2:])
            apa = int(folder.split('apa')[-1][0])

            chdir(input_dir+'/'+run+'/'+folder)
            dic_file_endpoint = [item for item in listdir() if item.endswith(input_json_name + '.json')][0]
            with open(dic_file_endpoint, 'r') as file:
                map_endpoint = json.load(file)

            ch_list = map_endpoint['fbk']+ map_endpoint['hpk']
            if ch_list != sorted(ch_list):
                print('\nEndpoint ' + ip + '--> Attention: channel ordering!')

            bias_list = map_endpoint['fbk_op_bias'] + map_endpoint['hpk_op_bias']
            while len(bias_list) < 5:
                bias_list.append(0)
                
            trim_list = [0] * 40
            
            trim_data= map_endpoint['fbk_op_trim'] + map_endpoint['hpk_op_trim']

            for i in range(len(ch_list)):
                trim_list[ch_list[i]] = trim_data[i]

            index_none = [index for index, value in enumerate(trim_list) if value is None]
            if len(index_none) > 0: 
                print('\nEndpoint ' + ip + ' --> Attention: Config channels ' + ' '.join(map(str, index_none)) + ' have Vop_trim_value = None --> it was set to zero!')
            else:
                print('\nEndpoint ' + ip + ' is okay!')
            
            trim_list = [0 if x is None else x for x in trim_list]
            
            map_complete[ip]['id'] = id
            map_complete[ip]['apa'] = apa
            map_complete[ip]['ch']= ch_list
            map_complete[ip]['bias'] = bias_list
            map_complete[ip]['trim'] = trim_list
            map_complete[ip]['ov'] = {'fbk': map_endpoint['fbk_ov'], 'hpk': map_endpoint['hpk_ov'] }
            map_complete[ip]['run'] = run

            

    print('\n\n')
    print(map_complete)

    chdir(f'{output_dir}/{run}')
    print()

    if output_json_name is None:
        output_json_name = f'complete_dic_FBK('+(str(map_endpoint['fbk_ov'])).replace('.', ',') + 'V)_HPK(' +(str(map_endpoint['hpk_ov'])).replace('.', ',') +'V)' 
    
    with open(f'{run}_{output_json_name}.json', "w") as fp:
        json.dump(map_complete, fp)

    for key, inner_dict in map_complete.items():
        if len(inner_dict) == 0:
            print(f'\nData about endpoint {key} not present! --> Incomplete json map!!\n')

    
    print('\n\nDONE\n\n')


if __name__ == "__main__":
    main()