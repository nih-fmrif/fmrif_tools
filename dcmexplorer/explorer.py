from __future__ import print_function, unicode_literals

import os
import argparse
import json
import pandas as pd

from common_utils.config import get_config
from common_utils.utils import init_log, log_shutdown, get_cpu_count, get_datetime, validate_dicom_tags
from glob import glob
from concurrent.futures import ThreadPoolExecutor, wait
from itertools import repeat
from dcmexplorer.utils import get_sample_dicoms, extract_compressed_dicom_metadata, \
                              extract_uncompressed_dicom_metadata


def explore_dicoms(settings):

    dicom_dir = settings["dicom_dir"]
    dicom_tags = settings["config"]["DICOM_TAGS"]
    nthreads = settings["nthreads"]
    log = settings["log"]

    created_log = False

    if not log:
        log = init_log(os.path.join(settings["out_dir"], "dcmexplorer_{}.log".format(get_datetime())),
                       log_name='dcmexplorer')
        created_log = True

    metadata_list = []

    # Collect tgz files in dcm_dir
    log.info("Collecting compressed Oxygen/Gold files...")
    tgz_files = glob(os.path.join(dicom_dir, "*.tgz"))
    log.info("Found {} compressed files.".format(len(tgz_files)))

    # Scan for unique dcm folders
    futures = []

    log.info("Scanning compressed files for unique scan series...")
    with ThreadPoolExecutor(max_workers=nthreads) as executor:
        for tgz_file in tgz_files:
            futures.append(executor.submit(get_sample_dicoms, tgz_file, log))
        wait(futures)

    compressed_dicoms = {}
    unique_series_count = 0
    for future in futures:
        if not future.exception():
            tgz_file, scans_list = future.result()
            compressed_dicoms[tgz_file] = scans_list
            unique_series_count += len(scans_list)

    log.info("Found {} unique scan series.".format(unique_series_count))

    if compressed_dicoms:

        exec_filelist = []
        for tgz_file in compressed_dicoms.keys():
            if compressed_dicoms[tgz_file]:
                dicoms = compressed_dicoms[tgz_file]
                exec_filelist.extend(zip(repeat(tgz_file), dicoms))

        log.info("Extracting metadata from scan series...")
        futures = []
        with ThreadPoolExecutor(max_workers=nthreads) as executor:
            for exec_pair in exec_filelist:
                tgz_file, dcm_file = exec_pair
                futures.append(executor.submit(extract_compressed_dicom_metadata, tgz_file, dcm_file, dicom_tags, log))
            wait(futures)

        for future in futures:
            if not future.exception():
                metadata_list.append(future.result())

    # Collect uncompressed files in dicom_dir
    log.info("Collecting unique Dicom files from uncompressed Oxygen/Gold scan directories...")

    dcm_files = glob(os.path.join(dicom_dir, "*/*/*/*.dcm"))

    seen_dirs = []
    scans_list = []

    for res in dcm_files:
        curr_dcm = res.strip()
        curr_dir = os.path.dirname(curr_dcm)
        if curr_dir not in seen_dirs:
            scans_list.append(curr_dcm)
            seen_dirs.append(curr_dir)

    log.info("Found {} unique scan series.".format(len(scans_list)))

    if scans_list:
        log.info("Extracting metadata from scan series...")
        futures = []
        with ThreadPoolExecutor(max_workers=nthreads) as executor:
            for dcm_file in scans_list:
                futures.append(executor.submit(extract_uncompressed_dicom_metadata, dcm_file, dicom_tags, log))
            wait(futures)

        for future in futures:
            if not future.exception():
                metadata_list.append(future.result())

    if metadata_list:
        metadata = pd.DataFrame(metadata_list, columns=metadata_list[0].keys())
    else:
        metadata = None

    if created_log:
        log_shutdown(log)

    return metadata


def main():

    start_datetime = get_datetime()

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "dicom_dir",
        help="Path to directory containing .tgz files from oxygen",
    )

    parser.add_argument(
        "out_dir",
        help="Output directory.",
    )

    parser.add_argument(
        "--config",
        help="Configuration file.",
        default=None
    )

    parser.add_argument(
        "--log",
        help="Log filename. Default will be oxy2bids_<timestamp>.log in the directory specified in the out_dir tag.",
        default=None
    )

    parser.add_argument(
        "--nthreads",
        help="number of threads to use when running this script. Use 0 for sequential run.",
        default=get_cpu_count(),
        type=int
    )

    cli_args = parser.parse_args()

    out_dir = os.path.abspath(cli_args.out_dir)

    # Init Logger
    if cli_args.log:
        log_fpath = os.path.join(out_dir, cli_args.log)
    else:
        log_fpath = os.path.join(out_dir, "oxy2bids_{}.log".format(start_datetime))

    log = init_log(log_fpath, 'dcmexplorer')

    # Load config file
    settings = {
        "config": get_config()
    }

    # If there is a custom config file, load it and overwrite any of the config fields
    # in the default config var
    if cli_args.config:
        try:
            with open(os.path.abspath(cli_args.config)) as cust_conf:
                custom_config = json.load(cust_conf)
            for key in custom_config.keys():
                settings["config"][key] = custom_config[key]
        except IOError:
            print("There was a problem loading the supplied configuration file. Aborting...")
            return

    log.info("Validating Dicom tags...")
    validate_dicom_tags(settings["config"]["DICOM_TAGS"], log=log)
    log.info("Successfully parsed Dicom tags!")

    # Normalize directories
    dicom_dir = os.path.abspath(cli_args.dicom_dir)

    settings["out_dir"] = out_dir
    settings["dicom_dir"] = dicom_dir
    settings["nthreads"] = cli_args.nthreads
    settings["log"] = log

    metadata = explore_dicoms(settings)

    if metadata is not None:
        # Export metadata as CSV file
        output_file = os.path.join(out_dir, "metadata_{}.csv".format(start_datetime))
        metadata.to_csv(output_file, sep=',', na_rep='', index=False)
    else:
        log.warning("No valid Dicom datasets found.")

    # Shutdown the logs
    log_shutdown(log)


if __name__ == "__main__":
    main()
