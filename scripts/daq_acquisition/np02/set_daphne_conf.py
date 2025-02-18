import os
import click
import json

@click.command()
@click.argument('details_path')
@click.argument('xml_path')
@click.argument('obj_name')
@click.option('--attenuators', type=str, default=None)
@click.option('--daphne_channels', type=str, default=None)
@click.option('--bias', type=str, default=None)
@click.option('--trim', type=str, default=None)
def cli(details_path, xml_path, obj_name, attenuators, daphne_channels, bias, trim):
    """ Script to update DAPHNE configuration files """
    if not os.path.exists(details_path):
        raise Exception('details.json does not exist at ', details_path)
    if not os.path.exists(xml_path):
        raise Exception('xml file does not exist at ', xml_path)
    with open(details_path, "r") as file:
         details_json_data = json.load(file)
     
    if bias:
        new_bias = [item.strip() for item in bias.split(",")]
        if len(new_bias) != 5:
            raise Exception('Error reading bias list, should be five comma separated values.')
        details_json_data["devices"][0]["channels"]["bias"] = new_bias

    if attenuators:
        new_attenuators = [item.strip() for item in attenuators.split(",")]
        if len(new_attenuators) != 5:
            raise Exception('Error reading attenuators list, should be five comma separated values.')
        details_json_data["devices"][0]["channels"]["attenuators"] = new_attenuators
    
    if daphne_channels:
        new_daphne_channels = [item.strip() for item in daphne_channels.split(",")]
        if len(daphne_channels) == 0:
            raise Exception('Error: Must provide non-empty list of channels.')
        details_json_data["devices"][0]["channels"]["indices"] = new_daphne_channels

    if trim:
        new_trim = [item.strip() for item in trim.split(",")]
        if len(new_trim) != 40:
            raise Exception('Error: list of trims must have a length of 40.')
        details_json_data["devices"][0]["channels"]["trim"] = new_trim
    
    # dump new config
    with open(details_path, "w") as file:
        json.dump(details_json_data, file, indent=4)
    details_dir = os.path.dirname(details_path)
    if not details_dir:
        details_dir = '.'
    output_path = details_dir + '/output.json'
    print('output path = ', output_path)
    command = f'python3 seed.py --details {details_path} --output {output_path}'
    print('seed command: ', command)

    command = f'add_daphne_conf {xml_path} {output_path} -n {obj_name}'
    print(command)
    os.system(command)
    # read back updated values to make sure they were set correctly
    with open(details_path, "r") as file:
        updated_data = json.load(file)
        if bias: 
            print("Updated bias values:", updated_data["devices"][0]["channels"]["bias"])    
        if attenuators: 
            print("Updated attenuator values:", updated_data["devices"][0]["channels"]["attenuators"])
        if daphne_channels:
            print("Updated channel values:", updated_data["devices"][0]["channels"]["indices"])
        if trim:
            print("Updated trim values:", updated_data["devices"][0]["channels"]["trim"])
        print('Updated details json')

if __name__ == '__main__':
    cli()



