import logging
import json

def run_acquisition(mode, conf):
    logging.info(f"Running data acquisition in {mode} mode with loaded configuration!")
    # TODO: implement acquisition using `conf`

def main(mode="cosmics", conf_path=None):
    if conf_path is None:
        logging.error("Configuration path must be provided.")
        raise ValueError("Configuration path is required.")
    
    try:
        with open(conf_path, 'r') as f:
            conf = json.load(f)
    except Exception as e:
        logging.error(f"Failed to load configuration: {e}")
        raise

    run_acquisition(mode, conf)

if __name__ == "__main__":
    main()
