#!/bin/sh

source ./config_utilities.sh

rm -rf logs/np0*_DAPHNE*.log


#np02


for comp in "CB"
do
    for conf in "calib"
    do
        ./gen_daqconf_config.py GEN_CONFIGS/daphne/gen_np02_daphne_$comp.json DAPHNE_CONFS/np02_confgen_daphne_$comp.json
        for PM in "ssh"
        do
            rm -rf DAPHNE_CONFS/np02_DAPHNE_$comp\_$conf\_$PM\_conf
            daphne_gen -c DAPHNE_CONFS/np02_confgen_daphne_$comp\_$PM.json -f DAPHNE_CONFS/np02_daphne_$comp\_$conf\_seed.json DAPHNE_CONFS/np02_DAPHNE_$comp\_$conf\_$PM\_conf >& logs/np02_DAPHNE_$comp\_$conf\_$PM.log &
        done
    done
done


wait

