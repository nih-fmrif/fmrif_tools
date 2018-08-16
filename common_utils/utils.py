from __future__ import print_function, unicode_literals

import os
import errno
import multiprocessing
import logging
import json
import pkg_resources

from datetime import datetime


def get_datetime():
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def get_cpu_count():
    return multiprocessing.cpu_count()


def init_log(log_fpath=None, log_name=None, debug=False):

    if log_name:
        log = logging.getLogger(log_name)
    else:
        log = logging.getLogger('oxy2bids')

    if debug:
        log.setLevel(logging.DEBUG)
    else:
        log.setLevel(logging.INFO)

    # Log formatter
    log_fmt = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Log Handler for console
    console_handler = logging.StreamHandler()
    if debug:
        console_handler.setLevel(logging.DEBUG)
    else:
        console_handler.setLevel(logging.INFO)

    console_handler.setFormatter(log_fmt)
    log.addHandler(console_handler)

    if log_fpath:
        # Log handler for file
        file_handler = logging.FileHandler(log_fpath)
        if debug:
            file_handler.setLevel(logging.DEBUG)
        else:
            file_handler.setLevel(logging.INFO)

        file_handler.setFormatter(log_fmt)
        log.addHandler(file_handler)

    return log


def log_shutdown(log):
    logging.shutdown()
    del log


def create_path(path, semaphore=None):

    if semaphore:
        semaphore.acquire()

    try:
        os.makedirs(path)
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise

    if semaphore:
        semaphore.release()


def validate_dicom_hex(tag, hex_str, log=None):

    valid = True

    dcm_hex_vals = hex_str.split(",")

    # Verify both a group and an element have been provided
    if len(dcm_hex_vals) != 2:
        err_msg = "Dicom tags must have two hexadecimal values, separated by a comma. The tag: {}: {} does" \
                  "not met these specifications.".format(tag, hex_str)
        log.error(err_msg) if log else print(err_msg)

        return False

    # Verify that the values provided for the group and the element are valid hex numbers
    dcm_group = dcm_hex_vals[0].strip()
    dcm_element = dcm_hex_vals[1].strip()

    try:
        int(dcm_group.strip(), 16)
    except ValueError:
        err_msg = "The group value {} in the tag {} is not a valid hexadecimal number.".format(dcm_group, tag)
        log.error(err_msg) if log else print(err_msg)
        valid = False

    try:
        int(dcm_element.strip(), 16)
    except ValueError:
        err_msg = "The element value {} in the tag {} is not a valid hexadecimal number.".format(dcm_element, tag)
        log.error(err_msg) if log else print(err_msg)
        valid = False

    return valid


def validate_dicom_tags(dicom_tags, log=None):

    valid = True

    for tag in dicom_tags.keys():

        curr_val = dicom_tags[tag]

        if type(curr_val) == str:

            if not validate_dicom_hex(tag, curr_val, log):
                valid = False

        elif type(curr_val) == list:

            for pair in curr_val:

                if type(pair) != str:
                    err_msg = "The value {} in the tag {} is not a valid hexadecimal number pair".format(pair, tag)
                    log.error(err_msg) if log else print(err_msg)
                    valid = False
                else:
                    if not validate_dicom_hex(tag, pair, log):
                        valid = False

    if not valid:
        err_msg = "Errors were found in the Dicom tags file."
        raise Exception(err_msg)


def get_config(custom_config=None):

    if custom_config and (custom_config not in ['3Ta', '3Tb', '3Tc', '3Td', 'BIDS']):
        # There is a user supplied config file that is not a default option, load it

        try:
            with open(str(custom_config)) as cfile:
                config = json.load(cfile)
        except IOError:
            raise Exception("There was a problem loading the supplied configuration file. Aborting...")

        validate_dicom_tags(config["DICOM_TAGS"])

        return config

    elif custom_config and (custom_config in ['3Ta', '3Tb', '3Tc', '3Td', 'BIDS']):
        # Specifies one of the default config files

        fmap = {
            '3Ta': '3Ta.json',
            '3Tb': '3Tb.json',
            '3Tc': '3Tc.json',
            '3Td': '3Td.json',
            'BIDS': 'bids.json',
        }

        config_file = pkg_resources.resource_filename("common_utils", "data/{}".format(fmap[custom_config]))

        with open(str(config_file)) as cfile:
            config = json.load(cfile)

        return config

    else:
        # No config file specified, used BIDS map

        config_file = pkg_resources.resource_filename("common_utils", "data/bids.json")

        with open(str(config_file)) as cfile:
            config = json.load(cfile)

        return config
