"""
Simple PDS waveform plotter.
"""

import sys

sys.path.append('src')

import pdstools

import time
import click
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from uproot import recreate
from numpy import array


@click.command()
@click.argument("filename", type=click.Path(exists=True))
@click.option("--channel", '-c', default=0,
              help="Channel to process and plot on. Default: 0")
@click.option("--num-fragments", '-n', default=10,
              help="Number of fragments to attempt loading. Default: 10")
@click.option("--quiet", '-q',
              help="Quiets debug outputs. Default: False.", is_flag=True)
@click.option("--start-offset", '-s', default=0,
              help="Starting fragment offset. Default: 0")
def main(filename, channel, num_fragments, quiet, start_offset):
    """ Simple PDS waveform plotter. """
    # Initializing
    data = pdstools.DAPHNEData(filename, quiet)
#    data.set_channels([channel,])
    data.set_channels([0,1,2,3,4,5,6,7])
    frag_list = data.get_fragment_paths()

    # Check that it starts loading with the bounds
    total_frags = len(frag_list)
    if start_offset >= total_frags:
        raise IndexError(
                "num_fragments >= the total amount of data fragments!"
        )

    f = recreate(f"pds_waveforms_run{data.run_id}_{data.file_index:04}_ch{channel}.root")
    
    # Loading and plotting    
    load_count = 0
    t0=0
    frag_idx = start_offset
    #with PdfPages(f"pds_waveforms_run{data.run_id}_{data.file_index:04}_ch{channel}.pdf") as pdf:    

        
    while (load_count < num_fragments) and (frag_idx < total_frags):
        wf,ch,timestamps = data.load_fragment(frag_list[frag_idx])
        
        if len(wf) > 0:  # Requested channel in this fragment
            if load_count==0:
                t0=timestamps[0]
            
            timestamps = (timestamps-t0)/100
            fragment = [load_count for i in range(len(ch))]            
            ttick = [[j for j in range(1024)] for i in range(len(ch))]
            if load_count==0:
                f["wf"] =     ({'adc': wf, 't':ttick, 'ts':timestamps,'ch':ch,'f':fragment})
            else:
                f["wf"].extend({'adc': wf, 't':ttick, 'ts':timestamps,'ch':ch,'f':fragment})


            #np.set_printoptions(threshold = np.inf)
            #for i in range(len(wf)):
            #    print (i, " -->", wf[i])
            #f[f"wf{load_count}"] = ({'adc': wf, 't':ttick, 'ch':ch})
                
            load_count += 1
        frag_idx += 1

    if (load_count < num_fragments) and (not quiet):
        print(f"INFO: Reached last fragment without getting {num_fragments} fragments.\n"
              +"      Plotting as is.")

    return 0


if __name__ == "__main__":
    main()
