from hdf5libs import HDF5RawDataFile
import daqdataformats
from daqdataformats import FragmentType

import detdataformats
from rawdatautils.unpack.daphne import *

from glob import glob
import numpy as np
from tqdm import tqdm
import argparse

# Define a function to extract fragment information
def extract_fragment_info(frag):
	frag_id = str(frag).split(' ')[3][:-1]
	fragType = frag.get_header().fragment_type
	
	if fragType == FragmentType.kDAPHNE.value:  # For self trigger
		trigger = 'self_trigger'
		timestamps = np_array_timestamp(frag)
		adcs = np_array_adc(frag)
		channels = np_array_channels(frag)
	elif fragType == 13:  # For full_stream
		trigger = 'full_stream'
		timestamps = np_array_timestamp_stream(frag)
		adcs = np_array_adc_stream(frag)
		channels = np_array_channels_stream(frag)[0]
	
	return trigger, frag_id, channels, adcs, timestamps



# Function to save data to binaries
def write_file(fout, lenwvfbytes: bytes, timestamps: np.ndarray, adcs:np.ndarray):
	fout.write(lenwvfbytes)
	fout.write(timestamps.tobytes())
	fout.write(adcs.tobytes())

"""
Read hdf5 files and convert it into binary files

Example
-------
>>> import numpy as np
... filename = "pds_waveforms_run025474_wf_ep111_ch13.dat"
... npts = np.fromfile(filename,dtype=np.uint32,count=1)[0]
... dt = np.dtype([
...     ('npts', np.uint32),
...     ('timestamp', np.uint64),
...     ('wvfs', (np.uint16,npts))])
... data = np.fromfile(filename, dtype=dt)
>>> len(data['wvfs'])
"""
if __name__ == "__main__":
	parse = argparse.ArgumentParser()
	parse.add_argument('-f', '--folder', type=str, help="Folder in which hdf5 files are located", default= '/afs/cern.ch/work/h/hvieirad/public/protoDUNE_HD_data/')
	parse.add_argument('-r', '--run', type=str, help='Run you which to process, ex: run025474', default="run025474")
	parse.add_argument("-ch", "--channels", type=int, nargs="+", help="(If empty, all 48 channels is analyzed). List of channels to be saved, ex: 13 15 (ordering is not required)")
	parse.add_argument("-nskip", "--nskip", type=int, help="Skip first nskip records")
	parse.add_argument("-dCh", "--debugCh", type=int,  help="Set a channel to be printed", default=None)
	parse.add_argument("-refresh", "--refresh", action='store_true', help='Ovewrite existing data')
	args = vars(parse.parse_args())

	
	folder    = args['folder']
	run       = args['run']
	nskip     = args['nskip']
	ch_to_save = [ ch for ch in range(48) ]
	if (args['channels'] is not None):
		ch_to_save = args['channels']
	debugCh = args['debugCh']
	
	nrecords  = None #None if you want to run all the folder

	geoids = [47244771330,51539738626,55834705922]
	ep = 111
	geoid_to_save = geoids[ep-111]

	if args['refresh']:
		for ch in ch_to_save:
			open(f"pds_waveforms_{run}_wf_ep{ep}_ch{ch}.dat","w").close()
	f_name_ch = { ch: open(f"pds_waveforms_{run}_wf_ep{ep}_ch{ch}.dat","ab") for ch in ch_to_save }

	det = 'HD_PDS'

	lenwvfbytes = 0 # lenght of waveform, will be extract in the code

	files = sorted(glob(f'{folder}/*{run}*.hdf5.copied'))
	if len(files) == 0:
		print(f"No file with ${run} found in ${folder}")
		exit(0)


	# Iterate through files
	for file in files:
		print(f'Reading {file}')
		h5_file = HDF5RawDataFile(file)
		records = h5_file.get_all_record_ids()
		
		if nrecords is None: nrecord = len(records)
		# Iterate through records
		for r in tqdm(records[nskip:nrecords]):
			
			frag = h5_file.get_frag(r, geoid_to_save)
			trigger, frag_id, channels, adcs, timestamps = extract_fragment_info(frag)

			if lenwvfbytes == 0 and len(adcs)>0:
				lenwvfbytes = (len(adcs[0])).to_bytes(4,'little')

			
			for ch_index, ch in enumerate(channels):
				if ch in ch_to_save:
					if ch == debugCh:
						print(frag_id, adcs)
					write_file(f_name_ch[ch], lenwvfbytes, timestamps[ch_index], adcs[ch_index])


