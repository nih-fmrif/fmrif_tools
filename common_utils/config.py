import json
import pkg_resources


def get_config():
    config_file = pkg_resources.resource_filename("common_utils", "data/config.json")
    with open(config_file) as cfile:
        config = json.load(cfile)
    return config
