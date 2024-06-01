# readme.md
This tool needs a fddaq environment version > 4.4.1

using a text editor set the variables in `seed` and generate the details seed:

```
./seed
```

using a test editor set the endpoints in `daphne_conf.json`

then, use the following command, using a meaningful name for the folder in the last argument to generate the final configuration:

```
./daphne_gen -c daphne_example_config.json -f seed.json daphne_conf2
```

## Usage
```
Usage: daphne_gen [OPTIONS] JSON_DIR

Options:
  -c, --config FILE       daphne_gen:

      boot:
          base_command_port (Default: 3333): Base port of application command endpoints
          capture_env_vars (Default: ['TIMING_SHARE', 'DETCHANNELMAPS_SHARE']): List of variables to capture from the environment
          disable_trace (Default: False): Do not enable TRACE (default TRACE_FILE is /tmp/trace_buffer_${HOSTNAME}_${USER})
          opmon_impl (Default: local): Info collector service implementation to use
          ers_impl (Default: local): ERS destination (Kafka used for cern and pocket)
          pocket_url (Default: 127.0.0.1): URL for connecting to Pocket services
          process_manager (Default: ssh): Choice of process manager
          k8s_image (Default: ghcr.io/dune-daq/alma9-run:develop): Which docker image to use
          run_control (Default: nanorc): Which run control to use
          controller_host (Default: localhost): Which host should the controller run on (only applicable with drunc)
          use_connectivity_service (Default: True): Whether to use the ConnectivityService to manage connections
          start_connectivity_service (Default: True): Whether to use the ConnectivityService to manage connections
          connectivity_service_threads (Default: 2): Number of threads for the gunicorn server that serves connection info
          connectivity_service_host (Default: localhost): Hostname for the ConnectivityService
          connectivity_service_port (Default: 15000): Port for the ConnectivityService
          connectivity_service_interval (Default: 1000): Publish interval for the ConnectivityService

      DaphneInput:
          slots (Default: [4, 5, 7, 9, 11, 12, 13]): List of the daphne to use, identified by slot
          biasctrl (Default: 4095): Biasctr to be used for all boards
          afe_gain (Default: 2667): Gain to be used for all afes across the boards
          channel_gain (Default: 2): Gain to be used for all channels across the boards
          channel_offset (Default: 1468): Offset to be used for all channels across the boards

          ADCConf: info to generate Reg4 value
              resolution (Default: False): true=12bit, false=14bit
              output_format (Default: True): true=Offset Binary, false=2s complement
              SB_first (Default: True): Which Significant bit comes first, true=MSB, false=LSB

          PGAConf: info to generate Reg51 value
              lpf_cut_frequency (Default: 0): cut frequency, only 4 values acceptable. 0=15MHz, 2=20MHz, 3=30MHz, 4=10MHz
              integrator_disable (Default: True): true=disabled, false=enabled
              gain (Default: False): true=30 dB, false=24 dB

          LNAConf: info to generate Reg52 value
              clamp (Default: 0): 0=auto setting, 1=1.5 Vpp, 2=1.15 Vpp, 3=0.6 Vpp
              integrator_disable (Default: True): true=disabled, false=enabled
              gain (Default: 2): 0=18 dB, 1=24 dB, 2=12 dB
          dump_buffers_directory (Default: ./): Where the dump_buffer command will write the spy buffer
          dump_buffers_n_samples (Default: 1024): How many samples to dump
  --host TEXT             host of the Daphne application  [default:
                          np04-srv-015]
  -f, --daphne-file PATH  daphne json with detailed configuration
  -h, --help              Show this message and exit.

```
