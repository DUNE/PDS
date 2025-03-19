import os
import click
import json
import xml.etree.ElementTree as ET

@click.command(help="details_path: path to main details file to extract configuration (required)")
@click.argument('details_path')
def cli(details_path):
    """Script to update DAPHNE configuration files extracting all information from details.json"""

    if not os.path.exists(details_path):
        raise Exception(f'details.json does not exist at {details_path}')

    with open(details_path, "r") as file:
        config = json.load(file)

    # Base working directory
    drunc_dir = config["drunc_working_dir"]

    # Extract paths and object names relative to drunc working directory
    daphne_details_path = os.path.join(drunc_dir, config["daphne_details"])
    xml_path = os.path.join(drunc_dir, config["oks_file"])
    obj_name = config["daphne_obj"]

    if not os.path.exists(daphne_details_path):
        raise Exception(f'Daphne details file does not exist at {daphne_details_path}')
    if not os.path.exists(xml_path):
        raise Exception(f'XML file does not exist at {xml_path}')

    # Load the daphne-specific configuration
    with open(daphne_details_path, "r") as file:
        daphne_json_data = json.load(file)

    # Update DAPHNE configuration with values from main details.json
    bias = [int(x) for x in config["bias"].split(",")]
    attenuators = [int(x) for x in config["attenuators"].split(",")]

    if len(bias) != 5 or len(attenuators) != 5:
        raise Exception('Bias and attenuator lists must each have exactly 5 values.')

    daphne_json_data["devices"][0]["channels"]["bias"] = bias
    daphne_json_data["devices"][0]["channels"]["attenuators"] = attenuators

    # Write back updated daphne_details file
    with open(daphne_details_path, "w") as file:
        json.dump(daphne_json_data, file, indent=4)

    details_dir = os.path.dirname(daphne_details_path) or '.'
    output_path = os.path.join(details_dir, 'output.json')
    seed_path = os.path.join(details_dir, 'seed.py')

    command = f'python3 {seed_path} --details {daphne_details_path} --output {output_path}'
    print('Running seed command:', command)
    os.system(command)

    command = f'add_daphne_conf {xml_path} {output_path} -n {obj_name}'
    print('Running XML update command:', command)
    os.system(command)

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
                for subkey in json_file.keys():
                    print(f'For key={subkey}, json={json_file[subkey]}')

    print('Updated DAPHNE configuration successfully.')

if __name__ == '__main__':
    cli()
