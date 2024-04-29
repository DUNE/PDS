# Scripts for Offline Analysis

## Simple Waveform Plots
`simple_waveform_plots.py` makes use of `pdstools` to plot the waveforms for a single channel on a given HDF5 file. The resulting plots appear as pages on a PDF file. For usage details, do `python simple_waveform_plots.py --help`. This script is intended to be an example for how `pdstools` can be used.

## IV curves analysis
`iv_ana.py` is the merge of Renan and Anna's codes to get breakdown voltage from ivcurves data. 
Run example: 
```bash 
python iv_ana.py --dir "/eos/experiment/neutplatform/protodune/experiments/ProtoDUNE-II/PDS_Commissioning/ivcurves/Apr-09-2024-run00" (--ips 104 --out .)
```
By default, all endpoints will be analyzed but you may want to analyze quickly just one of them.
This will produce two outputs:
    - Mon-day-year-runXX_fit.txt: where the breakdown voltages obtained are stored.
    - Mon-day-year-runXX_IVplots.pdf: all the plots needed to extract the breakdown voltage. 
This script has only the skeleton and all the functions used are stored in `iv_utl.py`.
Additionally, you can use `iv_run.py` to analyze all the folders and collect the output data in a unique Txt file.

If you want to test on a single file, we recommend using `iv_one.ipynb` notebook where the same procedure to get the plots is used.

### TO-DO LIST
- [x] Generalize Annas'script to analyze all the data independently on the branches
- [x] Safe in a unique file all the outputs from the fits and the possibility to run over all the folders with the same scripts
- [ ] Add in the fit plots more data?
- [ ] Add a json file or a function based on the date that selects the flip or *(-1) data particular treatment
- [ ] Check the missing folders (why?), change permissions 21-Apr, see if other iv folders could be merged now
- [ ] Deploy PulseShape method as it is not converging in general
- [ ] Avoid hard-coding conditions that may not work in general cases
- [ ] Move important prints to log.txt to be able to look at them later and remove as much as possible terminal printing to be more efficient
- [ ] Separate/check the V_op computation that is now inside iv_ana.py
- [ ] The Vbd given by the iv_trim/current branch is always "bad"? Investigate this to see if old data can be used
