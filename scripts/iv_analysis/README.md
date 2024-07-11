# IV CURVE ANALYSIS 
---
### What to do after acquiring IV curve
1. Compute the Breakdown voltage by using `Vbd_determination.py` 
2. Check if the acquired data (run) is good or not 
    * Check manually all plots created and write [here](https://docs.google.com/spreadsheets/d/1mbGphkpz9gtm8gb8Aemhs1N0M7QyICqJmlw3_XZAFR0/edit?usp=share_link) any anomalies
    * Use `Vbd_quality.py` to automatically check the behavior of this run with respect to previous runs
    * Use `Vbd_plot_single_run.py` to check the overall behaviour of all channels
    * Use `Vbd_plot_all_run.py` to check the behaviour in time of the breakdown voltage
3. Write [here](https://docs.google.com/spreadsheets/d/1mbGphkpz9gtm8gb8Aemhs1N0M7QyICqJmlw3_XZAFR0/edit?usp=share_link) if the run studied is good or not!
  
  
### If you want to change operation bias 
You have two possibilities:
* Use Vbd data from a given good run
* Use Vbd mean value obtained by comparing all good runs you have, by using `Vbd_best.py`


After making a decision, run `Vop_map.py` in order to create the json maps (or `Vop_determination.py` + `map_creation.py`).

---
___

## Python scripts
Description of all programs in the respository.

### Vbd_determination.py
It computes the Breakdown voltage of each channels, starting from IV root files.

It requires the following input parameters:
* `input_dir` : path of the directory related to the run studied (typically */eos/experiment/neutplatform/protodune/experiments/ProtoDUNE-II/PDS_Commissioning/ivcurves/{run}*)
* `output_dir` : path of the directory where to save data (by default *PDS/data/iv_analysis*)
* `endpoint` : the endpoint number to analyze (*104, 105, 107, 109, 111, 112, 113*) or *ALL* by default 
* `trimfit` : fit function to use for Trim IV curve (*poly* by default, or *pulse*)
* `map_path` : path of the map to use as reference (by default *PDS/maps/original_channel_map.json*)


Run example: 
```bash 
python Vbd_determination.py --input_dir /eos/experiment/neutplatform/protodune/experiments/ProtoDUNE-II/PDS_Commissioning/ivcurves/May-17-2024_run00 --output_dir afs/cern.ch/user/a/anbalbon/IV_curve/PDS/data/iv_analysis --endpoint ALL --trimfit poly  --map_path afs/cern.ch/user/a/anbalbon/IV_curve/PDS/maps/original_channel_map.json
```

It produces three output files:
* `{ip_address}_output.txt` for each endpoint, containg all info about the Bias and Trim IV curve and fit results. NaN values means missing channel or error in the fitting (see comments). Here the structure of the txt file.

| IP | File_name | APA | AFE | Config_CH | DAQ_CH | SIPM_type | Run | Endpoint_timestamp | Start_time | End_time | Bias_data_quality | Bias_min_I | Bias_max_I | Vbd_bias(DAC) | Vbd_bias(V) | Vbd_bias_error(V) | Bias_conversion_slope | Bias_conversion_intercept | Trim_data_quality | Trim_min_I | Trim_max_I | Fit_status | Poly_Vbd_trim(DAC) | Poly_Vbd_trim_error(DAC) | Pulse_Vbd_trim(DAC) | Pulse_Vbd_trim_error(DAC) | Vbd(V) | Vbd_error(V) |
|----|------------|-----|-----|-----------|--------|-----------|-----|--------------------|------------|----------|-------------------|------------|------------|---------------|-------------|--------------------|-----------------------|------------------------|-------------------|------------|------------|------------|--------------------|-------------------------|--------------------|-------------------------|--------|-------------|

* `{ip_address}_plots.pdf` for each endpoint, containing IV curve plots (both for bias and trim) of each channel
* `{ip_address}_Bias_IVplots_AFE.pdf` for each endpoint, containing a plot of Bias IV curve for each AFE 

---

### Vbd_quality.py
It allows you to check automatically if the Vbd results of a given run should be good or not by comparing them with previous runs.

It requires the following input parameters:
* `run` : run to analyze (by default, the last run)
* `good_runs` : list of good runs, used for the comparison (by default *['May-09-2024-run00', 'May-17-2024_run00', 'May-28-2024_run00', 'Jun-18-2024-run00']*)
* `input_dir` : path of the directory where all iv analysis results are saved (by default *PDS/data/iv_analysis*)
* `output_dir` : path of the directory where to save data (by default *PDS/data/iv_analysis*)
* `threshold` : theshold (in Volts) for the difference between the mean Vbd value and the current one (by default, *0.250 V)*


Run example: 
```bash 
python Vbd_quality.py --run Jul-02-2024-run00 --good_runs "['May-09-2024-run00','May-17-2024_run00','May-28-2024_run00','Jun-18-2024-run00']" --input_dir afs/cern.ch/user/a/anbalbon/IV_curve/PDS/data/iv_analysis  --output_dir afs/cern.ch/user/a/anbalbon/IV_curve/PDS/data/iv_analysis --threshold 0.250
```

It produces two output files:
* `Vbd_comparison.txt`, containing information about the analysis done for each channels, focusing on NAN value and discrepancy from the mean Vbd value (--> to be done!!!)
* `diff_histogram.pdf`, an histogram of the difference between the current Vbd value and the mean value obtained from previous runs

---

### Vbd_plot_single_run.py
It produces plots for monitoring the Vbd results of a given run.

It requires the following input parameters:
* `plot_type` : the plot to create (*CH_VBD_X_RUN*, *VB_HIST_X_RUN* or *ALL* by default)
* `input_dir` : path of the directory where all iv analysis results are saved (by default *PDS/data/iv_analysis*)
* `output_dir` : path of the directory where to save data (by default *PDS/data/iv_analysis*)
* `run` : run to analyze (for example *May-17-2024_run00*, *ALL* by default)

Run example: 
```bash 
python Vbd_plot_single_run.py --plot_type ALL --input_dir afs/cern.ch/user/a/anbalbon/IV_curve/PDS/data/iv_analysis  --output_dir afs/cern.ch/user/a/anbalbon/IV_curve/PDS/data/iv_analysis --run Jul-02-2024-run00
```

It produces two output files:
* `VB_HIST_X_RUN.pdf`, an histogram with all endpoints (FBK separated from HPK channels)
* `CH_VBD_X_RUN.pdf`, a plot where on the y axis there is the Vbd of each channel and on the x axis the name of the corresponding daq channel (all channels in the same plot)

---

### Vbd_plot_all_run.py
It produces plots for monitoring the breakdown voltage in time.

It requires the following input parameters:
* `plot_type` : the plot to create (*CH_VBD_VS_RUN*, *AFE_VBD_VS_RUN* and *ALL* by default)
* `input_dir` : path of the directory where all iv analysis results are saved (by default *PDS/data/iv_analysis*)
* `output_dir` : path of the directory where to save data (by default *PDS/data/iv_analysis*)
* `run_exluded` : runs to exlude from the analysis, by default we consider all data but for example you can remove *['Jun-07-2024-run00','Jul-02-2024-run00']*


Run example: 
```bash 
python Vbd_plot_all_run.py --plot_type ALL --input_dir afs/cern.ch/user/a/anbalbon/IV_curve/PDS/data/iv_analysis  --output_dir afs/cern.ch/user/a/anbalbon/IV_curve/PDS/data/iv_analysis
```

It produces two output files:
* `CH_VBD_plot.pdf`, a plot for each AFE (of each endpoint) with the channel Vbd as a function of time
* `AFE_VBD_VS_RUN.pdf`, a plot for each endpoint with mean AFE Vbd as a function of time

---

### Vbd_best.py
It computes the best estimation for the Breakdown voltage of each channel, by using the mean value of good runs.

It requires the following input parameters:
* `good_runs` : list of good runs (by default *['Apr-22-2024-run01','Apr-23-2024-run00','Apr-27-2024-run00','May-02-2024-run00','May-09-2024-run00', 'May-17-2024_run00', 'May-28-2024_run00', 'Jun-18-2024-run00']*)
* `input_dir` : path of the directory where all iv analysis results are saved (by default *PDS/data/iv_analysis*)
* `input_filename` : name of the file you want to read, containing Vbd info (by default = *output.txt*)
* `output_path` : path of the directory where data are saved (by default equal to *input_dir*)
* `output_dir_name` : name you want to give to the directory where data are saved  (**mandatory**)


Run example: 
```bash 
python Vbd_best.py --good_runs "['Apr-22-2024-run01','Apr-23-2024-run00','Apr-27-2024-run00','May-02-2024-run00','May-09-2024-run00','May-17-2024_run00','May-28-2024_run00','Jun-18-2024-run00']" --input_dir afs/cern.ch/user/a/anbalbon/IV_curve/PDS/data/iv_analysis --input_filename output.txt --output_path afs/cern.ch/user/a/anbalbon/IV_curve/PDS/data/iv_analysis --output_dir_name Mean_Vbd_data_1
```

It produces a `{ip_address}_output.txt` for each endpoint, which contains info about the mean value of Bias-Volt conversion parameters and of Vbd. A Nan value for Vbd now means that all the Vbd values associated with that channel are always Nan; if there is at least one no-Nan data then that is used. Here the structure of the txt file, where *Runs* is the list of runs used to evalute Vbd mean and Vbd_error(V) is the standard deviation of those values.

| IP | APA | AFE | Config_CH | DAQ_CH | SIPM_type | Run | Bias_conversion_slope | Bias_conversion_intercept | Vbd(V) | Vbd_error(V) |
|----|-----|-----|-----------|--------|-----------|------|-----------------------|-----------------------------|--------|-------------|


---

### Vop_determination.py
It computes the operation voltage of each channel, starting from the _output.txt file created by `Vbd_determination.py` or `Vbd_best.py`.

It requires the following input parameters:
* `input_dir` : path of the directory where the data you want to analyze are present (by default *PDS/data/iv_analysis/{run}*)
* `input_filename` : name of the txt file you want to read, containing Vbd info (by dafult *output.txt*)
* `output_dir` : path of the directory where to save data (by default equal to *input_dir*)
* `endpoint` :  endpoint number to analyze (*104, 105, 107, 109, 111, 112, 113*) or *ALL*, by default
* `fbk-ov` : overvoltage for FBK SiPM (by default *4.5 V*)
* `hpk-ov` : overvoltage for HPK SiPM (by default *3.0 V*)
* `json-name` : name for the json outputfile with info about operation voltage (by default: *{ip_address}_dic_FBK(fbk-ov)_HPK(hpk-ov)*)


Run example: 
```bash 
python Vop_determination.py --input_dir afs/cern.ch/user/a/anbalbon/IV_curve/PDS/data/iv_analysis/Jun-18-2024-run00 --input_filename output.txt --output_dir afs/cern.ch/user/a/anbalbon/IV_curve/PDS/data/iv_analysis/Jun-18-2024-run00s --endpoint ALL --fbk-ov 4.5 --hpk-ov 3 --json-name "dic_FBK(4,5)_HPK(3,0)"
```

It produces a json file for each endpoint, containing the operation voltage in terms of Bias and Trim DAC counts. None value for bias or trim means that there is a missing channel (disconnected or dead) or there is a fit error. Here the structure, where `apa` is the number of the APA, `fbk` is the list of FBK channels used, `hpk` is the list of HPK channels used, `fbk_op_bias` is the list of Bias DAC counts (one for each FBK AFE used), `fbk_op_trim` is the list of Trim DAC counts (one for each FBK channel used), `hpk_op_bias` is the list of Bias DAC counts (one for each HPK AFE used), `hpk_op_trim` is the list of Trim DAC counts (one for each HPK channel used), `timestamp` refers to the time of IV acquisition,  `run` refers to the name of the IV run, `ip` is the ip number of the endpoint, `fbk_ov` is the overvoltage (in Volts) applied to FBK SiPMs and `hpk_ov` is the overvoltage (in Volts) applied to HPK SiPMs.

```json
{"apa": 4,
"fbk": [0, 2, 5, 7],
"hpk": [],
"fbk_op_bias": [736],
"fbk_op_trim": [1119, 1247, 1078, 1186],
"hpk_op_bias": [],
"hpk_op_trim": [],
"timestamp": "Jun-18-2024_0833",
"run": "Jun-18-2024-run00",
"ip": "10.73.137.113",
"fbk_ov": 1.0,
"hpk_ov": 0.5}
```

---

### map_creation.py
It creates the complete map with operation voltage of each channels in terms of Bias and Trim DAC counts that must be used in the DAPHNE configuration. 

It requires the following input parameters:
* `run` : run to analyze (for example *Jun-18-2024-run00*)
* `input_dir` : path of the directory where all iv analysis results are saved (by default *PDS/data/iv_analysis*)
* `input-json-name` : name of the json file you want to read (produced by *Vbd_determination.py* or *IV_analysis.py*, by default: *dic*)
* `output_dir` : path of the directory where to save data (by default *PDS/data/iv_analysis*)
* `output-json-name` : name for the output json file with complete information about Vop (by default, *{run}_complete_dic_FBK(fbk-ov)_HPK(hpk-ov)*)



Run example: 
```bash 
python map_creation.py --run Jun-18-2024-run00 --input_dir afs/cern.ch/user/a/anbalbon/IV_curve/PDS/data/iv_analysis --input-json-name dic --output_dir afs/cern.ch/user/a/anbalbon/IV_curve/PDS/data/iv_analysis --output-json-name complete_dic
```

It produces a json file, containing all info about the operation voltage in terms of Bias and Trim DAC counts. Zero value for bias or trim means that we have no info about the corresponding channel (maybe we aren't using that channel, or the channel is dead/disconnected or there was a fit error). Here the structure, where `id` is equal to the last one/ two digits of the ip, `apa` is the number of the APA, `ch` is the list of channels used (both FBK and HPK), `bias` is a list of five elements refeing to Vop Bias DAC counts (one for each AFE), `trim` is a list of 40 elements refering to Vop Trim DAC (one for each channel), `ov` is a dic with overvoltage info (both for FBK AND HPK) and `run` refers to the origin of this data.

```json
{"10.73.137.104": { "id": 4,
                    "apa" : 1,
                    "ch": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
                    "bias": [799, 1134, 0, 0, 0],
                    "trim": [2141, 2012, 2153, 2023, 2371, 2188, 2096, 2044, 56, 127, 185, 133, 97, 54, 50, 108, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                    "ov": {"fbk": 4.5, "hpk": 3},
                    "run": "Jun-18-2024-run00"
                  },
"10.73.137.105": { "id": 5,
                   "apa" : 1,
                   "ch": [0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 13, 15, 17, 19, 20, 22],
                   "bias": [825, 819, 1158, 0, 0],
                   "trim": [984, 1056, 1048, 1064, 1081, 1045, 1016, 967, 1331, 0, 1198, 0, 0, 1269, 0, 1264, 0, 140, 0, 53, 111, 0, 148, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                   "ov": {"fbk": 4.5, "hpk": 3},
                   "run": "Jun-18-2024-run00"
                  },
"10.73.137.107": { "id": 7,
                   "apa" : 1,
                   "ch": [0, 2, 5, 7, 8, 10, 13, 15],
                   "bias": [820, 1159, 0, 0, 0],
                   "trim": [300, 0, 452, 0, 0, 622, 0, 302, 2196, 0, 70, 0, 0, 481, 0, 155, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                   "ov": {"fbk": 4.5, "hpk": 3},
                   "run": "Jun-18-2024-run00"
                  },
"10.73.137.109": { "id": 9,
                   "apa" : 2,
                   "ch": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39],
                   "bias": [803, 845, 1158, 1171, 1125],
                   "trim": [250, 271, 108, 188, 55, 280, 83, 290, 0, 0, 596, 0, 0, 630, 0, 0, 595, 525, 573, 58, 92, 327, 85, 178, 1133, 255, 1098, 1081, 416, 1119, 46, 1067, 466, 572, 49, 311, 78, 603, 228, 526],
                   "ov": {"fbk": 4.5, "hpk": 3},
                   "run": "Jun-18-2024-run00"
                  },
"10.73.137.111": { "id": 11,
                   "apa" : 3,
                   "ch": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39],
                   "bias": [808, 827, 817, 1204, 1197],
                   "trim": [164, 86, 73, 179, 120, 103, 72, 123, 1059, 958, 937, 944, 886, 1101, 854, 1120, 1614, 1758, 1652, 1423, 1428, 1641, 1323, 1491, 1893, 1392, 1114, 1375, 1435, 1680, 1377, 1012, 1854, 1140, 1620, 1154, 1168, 1255, 1179, 1216],
                   "ov": {"fbk": 4.5, "hpk": 3},
                   "run": "Jun-18-2024-run00"
                  },
"10.73.137.112": { "id": 12,
                   "apa" : 4,
                   "ch": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 34, 37, 39],
                   "bias": [1187, 1155, 1135, 1175, 1197],
                   "trim": [2124, 2166, 2119, 2140, 2091, 2128, 2139, 2143, 450, 3315, 388, 183, 57, 333, 105, 270, 394, 316, 1246, 383, 266, 48, 331, 265, 525, 601, 489, 1584, 587, 69, 600, 189, 1309, 0, 1191, 0, 0, 2014, 0, 2006],
                   "ov": {"fbk": 4.5, "hpk": 3},
                   "run": "Jun-18-2024-run00"
                  },
"10.73.137.113": { "id": 13,
                   "apa" : 4,
                   "ch": [0, 2, 5, 7],
                   "bias": [825, 0, 0, 0, 0],
                   "trim": [1110, 0, 1238, 0, 0, 1069, 0, 1177, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                   "ov": {"fbk": 4.5, "hpk": 3},
                   "run": "Jun-18-2024-run00"}
                  }
```

---

### Vop_map.py
It computes the Operation voltage of each channel, ofr a given overvoltage, and create a map for each endpoint and the complete map with in terms of Bias and Trim DAC counts that must be used in the DAPHNE configuration. 

It requires the following input parameters:
* `input_dir` : path of the directory where all iv analysis results are saved (by default *PDS/data/iv_analysis*)
* `run` : run to analyze (for example *Jun-18-2024-run00*)
* `input_filename` : name of the file you want to read containing Vbd info(produced by *Vbd_determination.py* or *IV_analysis.py*, by default: *output*)
* `output_dir` : path of the directory where to save data (by default *PDS/data/iv_analysis*)
* `fbk-ov` : overvoltage for FBK SiPM (by default *4.5 V*)
* `hpk-ov` : overvoltage for HPK SiPM (by default *3.0 V*)
* `json-name` : name for the output json files with  information about Vop (by default, *dic_FBK(fbk-ov)_HPK(hpk-ov)*)



Run example: 
```bash 
python map_creation.py --run Jun-18-2024-run00 --input_dir afs/cern.ch/user/a/anbalbon/IV_curve/PDS/data/iv_analysis --input-filename output --output_dir afs/cern.ch/user/a/anbalbon/IV_curve/PDS/data/iv_analysis --fbk-ov 3 --hpk-ov 2 --json-name dic
```

It produces json files, containing all info about the operation voltage in terms of Bias and Trim DAC counts. Zero value for bias or trim means that we have no info about the corresponding channel (maybe we aren't using that channel, or the channel is dead/disconnected or there was a fit error). It creates one json file for endpoint (as `Vop_determination.py`) and a complete map (as `map_creation.py`).


---

### IV_analysis.py

It computes the Breakdown voltage of each channels, starting from IV root files, and the operating voltage. NOTE: it's better to use Vbd_determination.py + Vop_determination.py (last algorithm versions), 

It requires the following input parameters:
* `input_dir` : path of the directory related to the run studied (typically */eos/experiment/neutplatform/protodune/experiments/ProtoDUNE-II/PDS_Commissioning/ivcurves/{run}*)
* `output_dir` : path of the directory where to save data (by default *PDS/data/iv_analysis*)
* `endpoint` : the endpoint number to analyze (*104, 105, 107, 109, 111, 112, 113*) or *ALL* by default 
* `trimfit` : fit function to use for Trim IV curve (*poly* by default, or *pulse*)
* `map_path` : path of the map to use as reference (by default *PDS/maps/original_channel_map.json*)
* `fbk-ov` : overvoltage for FBK SiPM (by default *4.5 V*)
* `hpk-ov` : overvoltage for HPK SiPM (by default *3.0 V*)
* `json-name` : name for the json outputfile with info about operation voltage (*dic* by default)

Run example: 
```bash 
python Vbd_determination.py --input_dir /eos/experiment/neutplatform/protodune/experiments/ProtoDUNE-II/PDS_Commissioning/ivcurves/May-17-2024_run00 --output_dir afs/cern.ch/user/a/anbalbon/IV_curve/PDS/data/iv_analysis --endpoint ALL --trimfit poly  --map_path afs/cern.ch/user/a/anbalbon/IV_curve/PDS/maps/original_channel_map.json --fbk-ov 4.5 --hpk-ov 3 --json-name dic
```
It returns the same output file of `Vbd_determination.py` + `Vop_determination.py`:
* `{ip_address}_output.txt` for each endpoint, containg all info about the Bias and Trim IV curve and fit results. NaN values means missing channel or error in the fitting (see comments). For more datails about the structure see `Vbd_determination.py`.
* `{ip_address}_plots.pdf` for each endpoint, containing IV curve plots (both for bias and trim) of each channel
* `{ip_address}_Bias_IVplots_AFE.pdf` for each endpoint, containing a plot of Bias IV curve for each AFE
* `dic.json` for each endpoint, containg the Voperation info of each channels in terms of Bias DAC counts (for each AFE) and Trim DAC counts (for each channels). None value for bias or trim means that there is a missing channel (disconnected or dead) or there is a fit error. For more datails about the structure see `Vop_determination.py`.

---

### IV_run_ALL.py

It runs `IV_analysis.py` on all runs, in */eos/experiment/neutplatform/protodune/experiments/ProtoDUNE-II/PDS_Commissioning/ivcurves*.
Attention: it is not update!


---

### Vbd_all_run.py

It runs `Vbd_determination.py` on all runs, in */eos/experiment/neutplatform/protodune/experiments/ProtoDUNE-II/PDS_Commissioning/ivcurves*.
