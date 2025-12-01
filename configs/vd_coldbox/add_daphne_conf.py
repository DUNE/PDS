#!/usr/bin/env python3

import conffwk
import os
import json
import sys


def add_daphne_conf(oksfile:str, object_name:str, json_file:str, timeout_ms:int = 1500):
    """Script to add a new DaphneConf object from a given json file"""

    print( "Adding file", json_file, "to object", object_name)

    db = conffwk.Configuration("oksconflibs:" + oksfile)

    with open(json_file, 'r') as file:
        data = json.load(file)

    print(data)

    schemafile='schema/appmodel/PDS.schema.xml'
    dal = conffwk.dal.module('dal', schemafile)



    ## first create the defaults
    def_channel = dal.DaphneV2Channel( "daphne-v2-default-channel",
                                       channel_id=100,
                                       gain=1,
                                       offset=2200,
                                       trim=0 )
    db.update_dal(def_channel)


    def_adc = dal.DaphneV2ADC( "daphne-v2-default-adc",
                               low_resolution=False,
                               output_offset_binary=True,
                               MSB_first=True)
    db.update_dal(def_adc)

    def_pga = dal.DaphneV2PGA( "daphne-v2-default-pga",
                               lpf_cut_frequency=4,
                               integrator_disable=True,
                               gain=False)
    db.update_dal(def_pga)

    def_lna = dal.DaphneV2LNA( "daphne-v2-default-lna",
                               clamp=0,
                               integrator_disable=True,
                               gain=2)
    db.update_dal(def_lna)

    def_afe = dal.DaphneV2AFE( "daphne-v2-default-afe",
                               afe_id=100,
                               attenuator=2666,
                               v_bias=0,
                               adc=def_adc,
                               pga=def_pga,
                               lna=def_lna)
    db.update_dal(def_afe)

    def_board = dal.DaphneV2BoardConf( "daphne-v2-default-board",
                                       bias_ctrl=0,
                                       self_trigger_threshold=0,
                                       default_channel=def_channel,
                                       default_afe=def_afe )
    db.update_dal(def_board)

    maps=[]

    ## Loop over the boards in the configuration
    for key, value in data.items() :
        channels = []
        afes = []

        ## create the channels
        raw_channels = value["channel_analog_conf"]
        raw_ids = raw_channels["ids"]
        raw_gains = raw_channels["gains"]
        raw_offsets = raw_channels["offsets"]
        raw_trims = raw_channels["trims"]
        for i, idx in enumerate(raw_ids):   ## idx in [0-39]
            c=dal.DaphneV2Channel( f"{object_name}-daphne-{key}-channel-{idx}",
                                   channel_id=idx,
                                   gain=raw_gains[i],
                                   offset=raw_offsets[i],
                                   trim=raw_trims[i] )
            db.update_dal(c)
            channels.append(c)

        ## create the afes
        raw_afes = value["afes"]
        raw_afe_ids = raw_afes["ids"]
        raw_afe_attenuators = raw_afes["attenuators"]
        raw_afe_biases = raw_afes["v_biases"]
        raw_adcs = raw_afes["adcs"]
        raw_adc_res = raw_adcs["resolution"]
        raw_adc_format = raw_adcs["output_format"]
        raw_adc_SB = raw_adcs["SB_first"]
        raw_lnas = raw_afes["lnas"]
        raw_lna_clamps = raw_lnas["clamp"]
        raw_lna_gains = raw_lnas["gain"]
        raw_lna_integrators = raw_lnas["integrator_disable"]
        raw_pgas = raw_afes["pgas"]
        raw_pga_cuts = raw_pgas["lpf_cut_frequency"]
        raw_pga_integrators = raw_pgas["integrator_disable"]
        raw_pga_gains = raw_pgas["gain"]
        for i, idx in enumerate(raw_afe_ids):   ## idx in [0-5]
            adc = dal.DaphneV2ADC( f"{object_name}-daphne-{key}-adc-{idx}",
                                   low_resolution = raw_adc_res[i],
                                   output_offset_binary = raw_adc_format[i],
                                   MSB_first=raw_adc_SB[i] )
            db.update_dal(adc)

            lna = dal.DaphneV2LNA(f"{object_name}-daphne-{key}-lna-{idx}",
                                  clamp=raw_lna_clamps[i],
                                  gain=raw_lna_gains[i],
                                  integrator_disable=raw_lna_integrators[i] )
            db.update_dal(lna)

            pga = dal.DaphneV2PGA(f"{object_name}-daphne-{key}-pga-{idx}",
                                  lpf_cut_frequency=raw_pga_cuts[i],
                                  gain=raw_pga_gains[i],
                                  integrator_disable=raw_pga_integrators[i] )
            db.update_dal(pga)

            afe = dal.DaphneV2AFE( f"{object_name}-daphne-{key}-afe-{idx}",
                                   afe_id=idx,
                                   attenuator=raw_afe_attenuators[i],
                                   v_bias=raw_afe_biases[i],
                                   adc=adc,
                                   lna=lna,
                                   pga=pga )
            db.update_dal(afe)
            afes.append(afe)

        ## create the board conf
        name = f"{object_name}-daphne-{key}-conf"
        detector = value["detector_id"]
        crate = value["crate_id"]
        slot = value["slot_id"]
        board = dal.DaphneV2BoardConf( name,
                                       bias_ctrl=value["bias_ctrl"],
                                       self_trigger_threshold=value["self_trigger_threshold"],
                                       full_stream_channels=value["full_stream_channels"],
                                       self_trigger_xcorr=value["self_trigger_xcorr"],
                                       tp_conf=value["tp_conf"],
                                       compensator=value["compensator"],
                                       inverter=value["inverter"],
                                       active_channels=channels,
                                       active_afes=afes,
                                       address=value["ip"],
                                       detector_id=detector,
                                       crate_id=crate,
                                       slot_id=slot,
                                       default_channel=def_channel,
                                       default_afe=def_afe )
        db.update_dal(board)

        link=dal.DaphneMap(name,
                           key=f"{detector}.{crate}.{slot}",
                           conf=board)
        db.update_dal(link)

        maps.append(link)


    ## create default objects, they will override old configurations


    new_conf = dal.DaphneConf(object_name,
                              timeout_ms=timeout_ms,
                              boards=maps,
                              default_v2_settings=def_board,
                              default_v3_settings=def_board )

    db.update_dal(new_conf)

    db.commit()


