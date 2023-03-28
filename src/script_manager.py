import os
from constants import *
import importlib

DIRNAME = os.path.dirname(__file__)


def list_scripts():
    """ List all scripts in the current directory """
    scripts = []
    for file in os.listdir(SCRIPTS_PATH):
        if file.endswith("_script.py"):
            # Get the script name from the file name
            scripts.append(file.split("_script.py")[0])
    return scripts


def get_all_script_info(logger=None):
    """ Get all script information """
    info_dict = dict()
    for script_name in list_scripts():
        module = importlib.import_module("scripts." + script_name + "_script")
        try:
            info_dict[script_name] = module.get_info()
        except AttributeError:
            info_dict[script_name] = {
                "name": script_name,
                "description": "Information not available for this script",
                "arguments": []
            }
            logger.error(f"No get_info function found for script {module.__name__}")
        continue
    return info_dict
