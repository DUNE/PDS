import os
import click
import json
import xml.etree.ElementTree as ET

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
def cli(details_path, xml_path, obj_name, attenuators, daphne_channels, bias, trim, mode, self_trigger_threshold):
    """ Script to update DAPHNE configuration files """
    if not os.path.exists(details_path):
        raise Exception('details.json does not exist at ', details_path)
    if not os.path.exists(xml_path):
        raise Exception('xml file does not exist at ', xml_path)
    if mode is not None and mode not in [0, 1]:
        raise Exception('Please specify a correct triggering mode (0 for full streaming, 1 for self-triggering), you provided ', mode)
    if mode == 1 and self_trigger_threshold is None:
        raise Exception('Since you are using self-triggering, please provide a self_trigger_threshold')
    
    with open(details_path, "r") as file:
        details_json_data = json.load(file)
    
    if bias:
        new_bias = [int(item.strip()) for item in bias.split(",")]
        if len(new_bias) != 5:
            raise Exception('Error reading bias list, should be five comma-separated values.')
        details_json_data["devices"][0]["channels"]["bias"] = new_bias

    if attenuators:
        new_attenuators = [int(item.strip()) for item in attenuators.split(",")]
        if len(new_attenuators) != 5:
            raise Exception('Error reading attenuators list, should be five comma-separated values.')
        details_json_data["devices"][0]["channels"]["attenuators"] = new_attenuators
    
    if daphne_channels:
        new_daphne_channels = [int(item.strip()) for item in daphne_channels.split(",")]
        if len(new_daphne_channels) == 0:
            raise Exception('Error: Must provide a non-empty list of channels.')
        details_json_data["devices"][0]["channels"]["indices"] = new_daphne_channels

    if trim:
        new_trim = [int(item.strip()) for item in trim.split(",")]
        if len(new_trim) != 40:
            raise Exception('Error: list of trims must have a length of 40.')
        details_json_data["devices"][0]["channels"]["trim"] = new_trim
    
    if mode is not None:
        if mode == 0:
            details_json_data["devices"][0]["mode"] = "full_streaming"
            details_json_data["devices"][0]["self_trigger_threshold"] = 0
        else:
            details_json_data["devices"][0]["mode"] = "self-trigger"
            details_json_data["devices"][0]["self_trigger_threshold"] = self_trigger_threshold

    with open(details_path, "w") as file:
        json.dump(details_json_data, file, indent=4)
    
    details_dir = os.path.dirname(details_path) or '.'
    output_path = os.path.join(details_dir, 'output.json')
    seed_path = os.path.join(details_dir, 'seed.py')
    
    command = f'python3 {seed_path} --details {details_path} --output {output_path}'
    print('seed command: ', command)
    os.system(command)
    
    command = f'add_daphne_conf {xml_path} {output_path} -n {obj_name}'
    print(command)
    os.system(command)
    
    root = ET.parse(xml_path)
    daphne_conf = root.find(".//obj[@class='DaphneConf'][@id='np02-daphne-running']")
    
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
                print('For key=', key, ', json=', json_file[key])
    
    with open(details_path, "r") as file:
        updated_data = json.load(file)
        print('Updated DAPHNE config')

if __name__ == '__main__':
    cli()
