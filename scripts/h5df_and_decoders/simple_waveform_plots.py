"""
Simple PDS waveform plotter.
"""

import pdstools

import click
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages


def plot_pdf_waveform(
        wf: np.ndarray,
        channel: int,
        fragment_index: int,
        pdf: PdfPages
) -> None:
    """
    Plot a waveform to a new page for the given PDF object.

    Parameters:
        wf (np.ndarray): A single waveform to plot.
        channel (int): Channel number for this waveform.
        fragment_index (int): Fragment index that this waveform was loaded from.
        pdf (PdfPages): PdfPages object to plot onto.

    Returns:
        Nothing. Only mutates the pdf object.
    """
    plt.figure(figsize=(6, 4))  # figsize is a style choice here.
    plt.plot(wf, 'k')

    plt.title(f"Fragment {fragment_index} PDS Channel {channel} Waveform")
    plt.xlabel("Ticks")
    plt.ylabel("ADC Count")

    plt.tight_layout()
    pdf.savefig()
    plt.close()

    return None


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
    data = pdstools.DAPHNEStreamData(filename, quiet)
    data.set_channels([channel,])
    frag_list = data.get_fragment_paths()

    # Check that it starts loading with the bounds
    total_frags = len(frag_list)
    if start_offset >= total_frags:
        raise IndexError(
                "num_fragments >= the total amount of data fragments!"
        )

    # Loading and plotting
    load_count = 0
    frag_idx = start_offset
    with PdfPages(f"pds_waveforms_run{data.run_id}_{data.file_index:04}.pdf") as pdf:
        while (load_count < num_fragments) and (frag_idx < total_frags):
            wf = data.load_fragment(frag_list[frag_idx])

            if len(wf) > 0:  # Requested channel in this fragment
                # wf.shape == (1, num time ticks), so use wf[0] for plt to play nice.
                plot_pdf_waveform(wf[0], channel, frag_idx, pdf)
                load_count += 1
            frag_idx += 1

    if (load_count < num_fragments) and (not quiet):
        print(f"INFO: Reached last fragment without getting {num_fragments} fragments.\n"
              +"      Plotting as is.")

    return 0


if __name__ == "__main__":
    main()
