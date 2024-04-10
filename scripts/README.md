# Python Scripts

## Simple Waveform Plots
`simple_waveform_plots.py` makes use of `pdstools` to plot the waveforms for a single channel on a given HDF5 file. The resulting plots appear as pages on a PDF file. For usage details, do `python simple_waveform_plots.py --help`. This script is intended to be an example for how `pdstools` can be used.

## IV curves analysis
`iv_analysis.py` is the merge of Renan and Ana individual codes to get breakdown voltage from ivcurves data. 
Run example: 
```bash 
    python iv_analysis.py --dir "/eos/experiment/neutplatform/protodune/experiments/ProtoDUNE-II/PDS_Commissioning/ivcurves/Apr-09-2024-run00" > /eos/experiment/neutplatform/protodune/experiments/ProtoDUNE-II/PDS_Commissioning/ivcurves/Apr-09-2024-run00/log.txt
```
This will save time when executing as the prints are stored in the log file and makes easy to debug possible errors.