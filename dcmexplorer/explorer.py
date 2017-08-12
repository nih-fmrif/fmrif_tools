from __future__ import print_function, unicode_literals

import os
import argparse
import json
import pkg_resources
import pandas as pd

from common_utils.utils import init_log, log_shutdown, get_cpu_count, get_datetime, validate_dicom_tags
from glob import glob
from concurrent.futures import ThreadPoolExecutor, wait
from itertools import repeat
from dcmexplorer.utils import get_sample_dicoms, extract_compressed_dicom_metadata, \
                              extract_uncompressed_dicom_metadata
from collections import OrderedDict


def explore_dicoms(dicom_dir, dicom_tags, nthreads=None, log=None):

    created_log = False

    if not log:
        log = init_log(os.path.join(os.getcwd(), "dcmexplorer_{}.log".format(get_datetime())))
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

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "dicom_dir",
        help="Path to directory containing .tgz files from oxygen",
    )

    parser.add_argument(
        "output_file",
        help="Path to directory containing .tgz files from oxygen",
    )

    parser.add_argument(
        "--dicom_tags",
        help="Path to a DICOM header tag specification file.",
        default=None
    )

    parser.add_argument(
        "--log",
        help="Log filepath. Default will be oxy2bids_<timestamp>.log in current working directory.",
        default=None
    )

    parser.add_argument(
        "--nthreads",
        help="number of threads to use when running this script. Use 0 for sequential run.",
        default=get_cpu_count(),
        type=int
    )

    settings = parser.parse_args()

    dicom_dir = os.path.abspath(settings.dicom_dir)

    # Init logging system
    if settings.log:
        log_fpath = os.path.abspath(settings.log)
    else:
        log_fpath = os.path.join(os.getcwd(), "dcmexplorer_{}.log".format(get_datetime()))

    log = init_log(log_fpath, 'dcmexplorer')

    # Use user-supplied Dicom tags if specified, otherwise use default tags in
    # dcmexplorer/data/dicom_tags.json
    if settings.dicom_tags:
        log.info("Parsing user-specified Dicom tags...")
        tag_fpath = os.path.abspath(settings.dicom_tags)
        with open(tag_fpath, 'r') as tags:
            dicom_tags = json.load(tags, object_pairs_hook=OrderedDict)
        log.info("Validating Dicom tags...")
        validate_dicom_tags(dicom_tags, log=log)
        log.info("Successfully parsed Dicom tags!")
    else:
        log.info("Loading default Dicom tags...")
        default_tags = pkg_resources.resource_filename("dcmexplorer", "data/dicom_tags.json")
        with open(default_tags, 'r') as tags:
            dicom_tags = json.load(tags, object_pairs_hook=OrderedDict)
        log.info("Validating default Dicom tags...")
        validate_dicom_tags(dicom_tags, log=log)
        log.info("Successfully loaded default Dicom tags!")

    metadata = explore_dicoms(dicom_dir, dicom_tags=dicom_tags, nthreads=settings.nthreads, log=log)

    if metadata is not None:
        # Export metadata as CSV file
        if os.path.basename(settings.output_file):
            output_file = os.path.abspath(settings.output_file)
        else:
            output_file = os.path.join(os.getcwd(), settings.output_file)

        metadata.to_csv(output_file, sep=',', na_rep='', index=False)
    else:
        log.warning("No valid Dicom datasets found.")

    # Shutdown the logs
    log_shutdown(log)


if __name__ == "__main__":
    main()
