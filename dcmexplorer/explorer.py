from __future__ import print_function, unicode_literals

import os
import argparse
import json
import pandas as pd

from common_utils.utils import init_log, log_shutdown, get_cpu_count, get_datetime, validate_dicom_tags, get_config
from glob import glob
from concurrent.futures import ThreadPoolExecutor, wait
from itertools import repeat
from dcmexplorer.utils import get_sample_dicoms, extract_compressed_dicom_metadata, \
                              extract_uncompressed_dicom_metadata


def explore_dicoms(dicom_dir, out_dir, dicom_tags, nthreads, log):

    created_log = False

    if not log:
        log = init_log(os.path.join(out_dir, "dcmexplorer_{}.log".format(get_datetime())),
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
        "--nthreads",
        help="number of threads to use when running this script. Use 0 for sequential run.",
        default=get_cpu_count(),
        type=int
    )

    settings = {}

    cli_args = parser.parse_args()

    settings["out_dir"] = os.path.abspath(cli_args.out_dir)

    # Init Logger
    log_fpath = os.path.join(settings["out_dir"], "dcmexplorer_{}.log".format(start_datetime))
    settings["log"] = init_log(log_fpath, 'dcmexplorer')

    # Load config file
    settings["config"] = get_config(cli_args.config) if cli_args.config else get_config()

    # Normalize directories
    settings["dicom_dir"] = os.path.abspath(cli_args.dicom_dir)

    settings["nthreads"] = cli_args.nthreads

    # Print the settings
    settings["log"].info(json.dumps({key: settings[key] for key in settings if key != 'log'}, sort_keys=True,
                                    indent=2))

    metadata = explore_dicoms(settings["dicom_dir"], settings["out_dir"], settings["config"]["DICOM_TAGS"],
                              settings["nthreads"], settings["log"])

    if metadata is not None:
        # Export metadata as CSV file
        output_file = os.path.join(settings["out_dir"], "metadata_{}.csv".format(start_datetime))
        metadata.to_csv(output_file, sep=',', na_rep='', index=False)
    else:
        settings["log"].warning("No valid Dicom datasets found.")

    # Shutdown the logs
    log_shutdown(settings["log"])


if __name__ == "__main__":
    main()
