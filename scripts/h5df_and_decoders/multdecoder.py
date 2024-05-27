from tqdm.contrib.concurrent import process_map
import argparse
from glob import glob
import subprocess
import re
import os

if __name__ == "__main__":
    parse = argparse.ArgumentParser()
    parse.add_argument("code", type=str, help="Code name")
    parse.add_argument('-j', '--jobs', type=str, help="File in which you put all parameters that you want to be executed...")
    parse.add_argument('-ncpu', '--ncpu', type=int, help="CPUs to be used (default=2)", default=2)
    parse.add_argument('-n', '--dry', action="store_true", help="Set as dry run")
    parse.add_argument('-o', '--output', action="store_true", help="Store output")
    args = vars(parse.parse_args())

    fileflags = args['jobs']
    code = args['code']
    getout = args['output']

    def parallel_func(it):
        ret = subprocess.run(it, capture_output=True, text=True)
        if getout:
            cmddone = '_'.join(it).replace('-','')
            with open(f'tmp_{cmddone}.tmp', 'w') as f:
                f.write(ret.stdout)
                f.write(ret.stderr)
        # if ret.stderr != '':
        #     print(ret.stderr)
        #     print(it)

    nproc = min(args['ncpu'], os.cpu_count())

    commands = [ ]
    with open(fileflags,'r') as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]
        for line in lines: 
            cmd = ['python', code]
            for flag in line.split():
                cmd.append(flag)
            commands.append(cmd)

    if args['dry']:
        print("Commands to be executed: ")
        for cmd in commands:
            print(' '.join(cmd))
        exit(0)
    print(f"Starting decoding with {nproc} processes")
    process_map(parallel_func, commands, max_workers=nproc)





    

