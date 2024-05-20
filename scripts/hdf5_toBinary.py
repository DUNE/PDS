from hdf5libs import HDF5RawDataFile
from daqdataformats import FragmentType

import detdataformats
from rawdatautils.unpack.daphne import *

import os
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

def get_files_list_glob(folder, run):
	# First try copied files
	files = sorted(glob(f'{folder}/*{run}*.hdf5.copied'))
	# If nothing, try normal
	if len(files) == 0:
		files = sorted(glob(f'{folder}/*{run}*.hdf5'))
	return files

def get_files_list_from_input(run):
	rucio_f_path = '/eos/experiment/neutplatform/protodune/experiments/ProtoDUNE-II/PDS_Commissioning/rucio_paths/'
	run = run.strip('run')
	files = []
	try: 
		f = open(f'{rucio_f_path}/{run}.txt', 'r')
	except FileNotFoundError:
		try:
			f = open(f'./{run}.txt', 'r')
		except:
			print(f"Could not find the list of files as {run}.txt in {rucio_f_path} nor locally.")
			exit(0)
	files = [ line.strip() for line in f.readlines() if run in line.strip() ]
	return files


"""
Read hdf5 files and convert it into binary files.
Example of usage:

python hdf5_toBinary.py -r run025474 --rucio --refresh -ch 40 42 -geoid 111

python hdf5_toBinary.py -r run025474 -f /path/to/files/ --refresh -ch 40 42 -geoid 111 -n 

Example
-------
>>> import numpy as np
... filename = "pds_waveforms_run025474_wf_ep111_ch13.dat"
... npts = np.fromfile(filename,dtype=np.uint32,count=1)[0]
... dt = np.dtype([
...     ('npts', np.uint32),
...     ('timestamps', np.uint64),
...     ('wvfs', (np.uint16,npts))])
... data = np.fromfile(filename, dtype=dt)
>>> len(data['wvfs'])
"""
if __name__ == "__main__":
	parse = argparse.ArgumentParser()
	parse.add_argument('-f', '--folder', type=str, help="Folder in which hdf5 files are located", default= '/afs/cern.ch/work/h/hvieirad/public/protoDUNE_HD_data/')
	parse.add_argument('-r', '--run', type=str, help='Run you which to process, ex: run025474', default="run025474")
	parse.add_argument('-rucio','--rucio', action='store_true', help='Set this option to automaticly grab runs from rucio entries\n\
					The files are located at /eos/experiment/neutplatform/protodune/experiments/ProtoDUNE-II/PDS_Commissioning/rucio_paths', default=None)
	parse.add_argument('-outpath', '--outputPath', type=str, help='Path for the output', default="/afs/cern.ch/work/h/hvieirad/public/protoDUNE_HD_data_decoded/")
	parse.add_argument("-ch", "--channels", type=int, nargs="+", help="(If empty, all 48 channels is analyzed). List of channels to be saved, ex: 13 15 (ordering is not required)")
	parse.add_argument("-nskip", "--nskip", type=int, help="Skip first nskip records, set to -100 for a quicky processing", default=0)
	parse.add_argument("-dCh", "--debugCh", type=int,  help="Set a channel to be printed", default=None)
	parse.add_argument("-refresh", "--refresh", action='store_true', help='Ovewrite existing data')
	parse.add_argument("-geoid", "--geoid", type=int, help='geoid: 111, 112 or 113', default=111)
	parse.add_argument("-n", "--dry", action='store_true', help='Dry run, output files to be processed')
	parse.add_argument("-check", "--check_exist", action='store_true', help='Check if files already exist, ask to confirm before overwriting it')
	args = vars(parse.parse_args())

	
	folder    = args['folder']
	run       = args['run']
	# safe format of run number
	run = f'run0{int(run.strip("run"))}'
	nskip     = args['nskip']

	ch_to_save = [ ch for ch in range(48) ]
	if (args['channels'] is not None):
		ch_to_save = args['channels']

	debugCh = args['debugCh']

	outputDir = f'{args["outputPath"]}/{run}'
	userucio = args['rucio']
	
	nrecords  = None #None if you want to run all the folder

	geoids = [47244771330,51539738626,55834705922]
	ep = args['geoid']
	geoid_to_save = geoids[ep-111]
	isdry = args['dry']


	if not os.path.exists(outputDir):
		# Create the directory
		os.makedirs(outputDir, exist_ok=True)
	f_name_ch = { ch: f"{outputDir}/pds_waveforms_{run}_wf_ep{ep}_ch{((ep-100)*100)+ch}.dat" for ch in ch_to_save }
	isempty: bool = True
	for ch in ch_to_save:
		isempty &= not os.path.isfile(f_name_ch[ch])
	if not isempty:
		print("WARNING: One or more files already exist!\n")
		if args['check_exist']:
			typeoverwrite = "Overwrite" if args['refresh'] else "Append on"
			user_input = input(f'{typeoverwrite} it anyway? (yes/no)? ')
			yes_choices = ['yes', 'y']
			if user_input.lower() not in yes_choices:
				exit(0)
	if args['refresh']:
		for ch in ch_to_save:
			open(f_name_ch[ch], "w").close()
	f_wvf_ch = { ch: open(f_name_ch[ch], 'ab') for ch in ch_to_save }

	det = 'HD_PDS'

	lenwvfbytes = 0 # lenght of waveform, will be extract in the code



	if not userucio:
		files = get_files_list_glob(folder, run)
	else:
		files = get_files_list_from_input(run)

	if len(files) == 0:
		print(f"No file with {run} found in {folder}")
		exit(0)


	if isdry:
		print("Files to be processed:")
		for file in files:
			print(file)
		print(f"Channels to be saved: {ch_to_save}")
		print(f"Output file name")
		for fname in f_name_ch.items():
			print(fname)

		exit(0)

	# Iterate through files
	totalev = 0
	totaldouble = 0
	timestamp_list = {ch: [] for ch in ch_to_save}
	for file in files:
		print(f'Reading {file}')
		h5_file = HDF5RawDataFile(file)
		records = h5_file.get_all_record_ids()
		
		if nrecords is None: nrecord = len(records)


		inittime = 0
		# Iterate through records
		for r in tqdm(records[nskip:nrecords]):
			

			thre_head = h5_file.get_trh(r)

			timestamp = thre_head.get_header().trigger_timestamp
			if inittime == timestamp:
				continue
			else:
				inittime = timestamp

			frag = h5_file.get_frag(r, geoid_to_save)
			trigger, frag_id, channels, adcs, timestamps = extract_fragment_info(frag)

			if lenwvfbytes == 0:
				if len(adcs)>0:
					lenwvfbytes = (len(adcs[0])).to_bytes(4,'little')

			for ch_index, ch in enumerate(channels):
				if ch in ch_to_save:
					if timestamps[ch_index] not in timestamp_list[ch]:
						if ch == debugCh:
							# print(frag_id, adcs)
							totalev+=1
						timestamp_list[ch].append(timestamps[ch_index])
						write_file(f_wvf_ch[ch], lenwvfbytes, timestamps[ch_index], adcs[ch_index])
						# totalev+=1
					else:
						if ch == debugCh:
							# print("Removing duplicated...")
							totaldouble+=1

	for ch in ch_to_save:
		f_wvf_ch[ch].close()
		if os.path.getsize(f_name_ch[ch]) == 0:
			os.remove(f_name_ch[ch])
	print(totaldouble, totalev)

	

