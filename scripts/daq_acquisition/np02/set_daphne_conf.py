import os
import click
import json
import xml.etree.ElementTree as ET
import pprint
import logging
from datetime import datetime

def RaiseAndLogError(message):
    logging.error('Error: ' + message)
    raise RuntimeError(message)

@click.command(help="details_path: path to details file to modify (required) \n \
                     xml_path: path to DAPHNE configuration XML file (required) )\n \
                     obj_name: name of object in XML to modify (required)")
@click.argument('details_path')
@click.argument('xml_path')
@click.argument('obj_name')
@click.option('--attenuators', type=str, default=None, help="VGAIN values for the 5 AFEs, e.g. 2600,2600,2600,2600,2600 (optional)")
@click.option('--daphne_channels', type=str, default=None, help="list of DAPHNE channels, e.g. 0,1,2,3 (optional)")
@click.option('--bias', type=str, default=None, help="bias DAC values for the 5 AFEs, e.g. 100,100,100,100,100 (optional)")
@click.option('--trim', type=str, default=None, help="trim values to use, expects 40 elements in comma sep. list (optional)")
@click.option('--mode', type=int, default=None, help="trigger mode (0 for full streaming, 1 for self-triggering)")
@click.option('--self_trigger_threshold', type=int, default=None, help="self-triggering threshold in ADCs (optional)")
@click.option('--offsets', type=str, default=None, help="offsets to use for each channels, expects 40 elements in comma sep. list (optional)")
def cli(details_path, xml_path, obj_name, attenuators, daphne_channels, bias, trim, mode, self_trigger_threshold, offsets):
    """ Script to update DAPHNE configuration files 
        Author: Sam Fogarty
    """
    details_dir = os.path.dirname(details_path) or '.' # assumes output.json and seed.py in same dir as details.json
    log_filename = os.path.join(details_dir, 'log', datetime.now().strftime("daphne_config_log_%Y-%m-%d_%H-%M-%S.log"))
    os.system(f"mkdir -p {os.path.join(details_dir, 'log')}")
    logging.basicConfig(
        filename=log_filename,
        filemode="w",  # Overwrite each time (use "a" for append mode)
        format="%(asctime)s - %(levelname)s - %(message)s",
        level=logging.INFO
    )
    logging.info(f'details_path = {details_path}')
    logging.info(f'xml_path = {xml_path}')
    logging.info(f'Modifying object: {obj_name}')
    print(f'logs being stored to {log_filename}')
    if not os.path.exists(details_path):
        RaiseAndLogError(f'details.json does not exist at {details_path}')
    if not os.path.exists(xml_path):
        RaiseAndLogError(f'xml file does not exist at {xml_path}')
    if mode is not None and mode not in [0, 1]:
        RaiseAndLogError(f'Please specify a correct triggering mode (0 for full streaming, 1 for self-triggering), you provided {mode}')
    if mode == 1 and self_trigger_threshold is None:
        RaiseAndLogError('Since you are using self-triggering, please provide a self_trigger_threshold')
    
    # load details.json which we will modify
    with open(details_path, "r") as file:
        try:
            details_json_data = json.load(file)
        except:
            RaiseAndLogError('Error opening details.json file.')
    
    # apply modifications based on user inputs to the configuration json
    if bias:
        new_bias = [int(item.strip()) for item in bias.split(",")]
        if len(new_bias) != 5:
            RaiseAndLogError('Error reading bias list, should be five comma-separated values.')
        details_json_data["devices"][0]["channels"]["bias"] = new_bias
    if attenuators:
        new_attenuators = [int(item.strip()) for item in attenuators.split(",")]
        if len(new_attenuators) != 5:
            RaiseAndLogError('Problem reading attenuators list, should be five comma-separated values.')
        details_json_data["devices"][0]["channels"]["attenuators"] = new_attenuators
        logging.info(f'Setting VGAIN values to {new_attenuators}')
    if daphne_channels:
        new_daphne_channels = [int(item.strip()) for item in daphne_channels.split(",")]
        if len(new_daphne_channels) == 0:
            RaiseAndLogError('Error: Must provide a non-empty list of channels.')
        details_json_data["devices"][0]["channels"]["indices"] = new_daphne_channels
        logging.info(f'Setting channels list to {new_daphne_channels}')
    if trim:
        new_trim = [int(item.strip()) for item in trim.split(",")]
        if len(new_trim) != 40:
            RaiseAndLogError('Error: list of trims must have a length of 40.')
        details_json_data["devices"][0]["channels"]["trim"] = new_trim
        logging.info(f'Setting trims list to {new_trim}')
    if mode is not None:
        if mode == 0:
            details_json_data["devices"][0]["mode"] = "full_streaming"
            details_json_data["devices"][0]["self_trigger_threshold"] = 0
            logging.info('Setting mode to full streaming')
        else:
            details_json_data["devices"][0]["mode"] = "self-trigger"
            details_json_data["devices"][0]["self_trigger_threshold"] = self_trigger_threshold
            logging.info(f'Setting mode to self-trigger, with threshold of {self_trigger_threshold}')
    if offsets:
        new_offsets = [int(item.strip()) for item in offsets.split(",")]
        if len(new_offsets) != 40:
            RaiseAndLogError('Error: list of offsets must have a length of 40.')
        details_json_data["devices"][0]["channels"]["offsets"] = new_offsets
        logging.info(f'Setting offsets to {new_offsets}')
    with open(details_path, "w") as file: # replace details file with updated one
        json.dump(details_json_data, file, indent=4)
    
    output_path = os.path.join(details_dir, 'output.json')
    seed_path = os.path.join(details_dir, 'seed.py')
    
    # overwrite output.json with info from details.json
    command = f'python3 {seed_path} --details {details_path} --output {output_path}'
    logging.info(f'seed command: {command}')
    os.system(command)
    
    # update object with new DAPHNE config
    command = f'add_daphne_conf {xml_path} {output_path} -n {obj_name}'
    logging.info(f'add daphne conf command: {command}')
    os.system(command)
    
    # print configuration as it is inside XML file
    root = ET.parse(xml_path)
    daphne_conf = root.find(f".//obj[@class='DaphneConf'][@id='{obj_name}']")
    
    if daphne_conf is not None:
        attributes = {}
        for attr in daphne_conf.findall("attr"):
            attr_name = attr.get("name")
            attr_type = attr.get("type")
            attr_val = attr.get("val")
            attributes[attr_name] = {"type": attr_type, "value": attr_val}
    
    for key, value in attributes.items():
        if key == 'json_file':
            json_file = json.loads(value['value'])
            for key in json_file.keys():
                logging.info(f'In the DAPHNE config XML, for key {key}, the stored json = {json_file[key]}')
    
    with open(details_path, "r") as file:
        updated_data = json.load(file)
        logging.info('Finished updating DAPHNE config')

if __name__ == '__main__':
    cli()
