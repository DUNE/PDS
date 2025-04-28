import logging
import os
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from pds.core.seed import generate_seeds

CONFIGURATIONS = [
    "np02_daphne_full_mode",
    "np02_daphne_full_mode_bias_off",
    "np02_daphne_selftrigger",
    "np02_daphne_selftrigger_bias_off"
]

def pretty_compact_json(obj, indent=2):
    def _dump(obj, level):
        spacing = ' ' * (level * indent)
        if isinstance(obj, dict):
            items = []
            for k, v in obj.items():
                dumped = _dump(v, level + 1)
                items.append(f'{spacing}{" " * indent}"{k}": {dumped}')
            return '{\n' + ',\n'.join(items) + f'\n{spacing}}}'
        elif isinstance(obj, list):
            items = [_dump(v, level + 1) for v in obj]
            return '[\n' + ',\n'.join(f'{" " * ((level + 1) * indent)}{item}' for item in items) + f'\n{spacing}]'
        else:
            return json.dumps(obj)
    return _dump(obj, 0)

def main(mode=None, conf_path=None):
    if conf_path is None:
        logging.error("Configuration path must be provided.")
        raise ValueError("Configuration path is required.")

    conf_path = Path(conf_path)

    if not conf_path.exists():
        raise FileNotFoundError(f"conf.json does not exist at {conf_path}")

    with open(conf_path, "r") as file:
        original_config = json.load(file)

    config = original_config.copy()

    temp_details_path = None

    if mode is not None:
        config["mode"] = mode

    temp_conf_path = None
    if mode is not None:
        temp_conf_path = conf_path.parent / "conf_temp.json"
        temp_details_path = conf_path.parent / "temp_details.json"
        with open(temp_conf_path, "w") as f:
            json.dump(config, f, indent=2)
        working_conf_path = temp_conf_path
    else:
        working_conf_path = conf_path

    try:
        with open(working_conf_path, "r") as file:
            config = json.load(file)

        drunc_dir = Path(config["drunc_working_dir"])
        mode = config["mode"]

        daphne_details_path = drunc_dir / config["daphne_details"]
        xml_path = drunc_dir / config["oks_file"]

        if not daphne_details_path.exists():
            raise FileNotFoundError(f"Daphne details file does not exist at {daphne_details_path}")
        if not xml_path.exists():
            raise FileNotFoundError(f"XML file does not exist at {xml_path}")

        # Load the DAPHNE-specific configuration
        with open(daphne_details_path, "r") as file:
            daphne_json_data = json.load(file)

        if mode == "noise":
            bias = [0 for _ in range(5)]
        else:
            bias = [int(x) for x in config["bias"].split(",")]

        attenuators = [int(x) for x in config["attenuators"].split(",")]

        if len(bias) != 5 or len(attenuators) != 5:
            raise ValueError("Bias and attenuator lists must each have exactly 5 values.")

        daphne_json_data["devices"][0]["channels"]["bias"] = bias
        daphne_json_data["devices"][0]["channels"]["attenuators"] = attenuators

        daphne_json = pretty_compact_json(daphne_json_data)

        # Write updated daphne_config.json
        daphne_config_path = daphne_details_path.parent / "daphne_config.json"
        with open(daphne_config_path, "w") as f:
            f.write(daphne_json)

        logging.info(f"✅ Updated DAPHNE config: {daphne_config_path}")

        # Run seed script to generate configurations
        logging.info(f"📢 Generating seeds from {daphne_config_path}")
        generate_seeds(daphne_config_path)

        # Update XML file using add_daphne_conf
        for config_name in CONFIGURATIONS:
            output_path = daphne_details_path.parent / (config_name + '.json')
            command = f'add_daphne_conf {xml_path} {output_path} -n {config_name}'
            logging.info(f"📢 Running XML update command: {command}")
            os.system(command)

            root = ET.parse(xml_path)
            daphne_conf = root.find(f".//obj[@class='DaphneConf'][@id='{config_name}']")

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
                            logging.info(f"ℹ️ For key={subkey}, json={json_file[subkey]}")

        logging.info("✅ Updated DAPHNE configuration successfully.")

    finally:
        if temp_details_path and temp_details_path.exists():
            logging.info(f"🧹 Cleaning up temporary details file: {temp_details_path}")
            os.remove(temp_details_path)

if __name__ == "__main__":
    main()
