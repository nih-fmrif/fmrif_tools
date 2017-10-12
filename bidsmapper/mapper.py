from __future__ import print_function, unicode_literals

import os
import json
import pandas as pd
import argparse

from glob import glob
from common_utils.config import get_config
from common_utils.utils import init_log, log_shutdown, get_cpu_count, get_datetime
from bidsmapper.utils import DicomScan, dicom_parser, get_unique_dicoms_from_compressed
from bidsmapper.constants import LOG_MESSAGES
from concurrent.futures import ThreadPoolExecutor, wait


def gen_map(settings):

    dicom_dir = settings["dicom_dir"]
    nthreads = settings["nthreads"]
    log = settings["log"]
    heuristics = settings["config"]["BIDS_TAGS"]

    exec_list = []

    # First collect representative Dicom scans from each compressed Oxygen/Gold file, and then do the
    # same for any present uncompressed files

    log.info("Searching for Compressed Oxygen\Gold files in {}".format(dicom_dir))

    compressed_files = glob(os.path.join(dicom_dir, "*.tgz"))

    log.info("Found {} compressed files".format(len(compressed_files)))

    if compressed_files:

        with ThreadPoolExecutor(max_workers=nthreads) as executor:

            futures = []

            for compressed_file in compressed_files:

                futures.append(executor.submit(get_unique_dicoms_from_compressed, compressed_file, dicom_dir, log))

            wait(futures)

            for future in futures:
                if future.result():
                    exec_list.extend(future.result())

    compressed_dcm_count = len(exec_list)
    log.info("Found {} DICOM series in {} the compressed files".format(compressed_dcm_count, len(compressed_files)))

    # Now do the same for uncompressed files
    log.info("Searching for uncompressed Oxygen\Gold DICOM series in {}".format(dicom_dir))

    uncompressed_dicoms = glob(os.path.join(dicom_dir, "*/*/*/*.dcm"))
    uncompressed_rt = glob(os.path.join(dicom_dir, "*/*/realtime/*.1D"))

    mr_folders_checked = []
    uncompressed_dicom_scans = []

    for scan in uncompressed_dicoms:

        scan = scan.strip()
        curr_dir = os.path.dirname(scan)

        if curr_dir not in mr_folders_checked and scan.endswith(".dcm"):

            uncompressed_dicom_scans.append(scan)
            mr_folders_checked.append(curr_dir)

    for dicom_file in uncompressed_dicom_scans:

        dicom_scan = DicomScan(scan_path=dicom_file, dicom_dir=dicom_dir, compressed=False)
        scan_name = "scan_{}".format(dicom_scan.get_scan_dir().split("/")[-1].split("_")[-1])

        for rt_file in uncompressed_rt:
            if ("ECG" in rt_file) and (scan_name in rt_file):
                dicom_scan.set_cardio(rt_file)
            elif ("Resp" in rt_file) and (scan_name in rt_file):
                dicom_scan.set_resp(rt_file)

        exec_list.append(dicom_scan)

    uncompressed_dcm_count = len(exec_list) - compressed_dcm_count
    log.info("Found {} unique DICOM series in the uncompressed directories.".format(uncompressed_dcm_count))

    # Parse the results
    with ThreadPoolExecutor(max_workers=nthreads) as executor:

        futures = []

        for scan in exec_list:

            futures.append(executor.submit(dicom_parser, scan, heuristics, log))

        wait(futures)

    parsed_results = []
    for future in futures:
        if future.result():
            parsed_results.append(future.result())

    mapping_df = None

    if parsed_results:

        mapping_df = pd.DataFrame(parsed_results, columns=parsed_results[0].keys())

        # Set the BIDS subjects based on unique patient id
        unique_ids = mapping_df['patient_id'].unique()
        subject_padding = len(str(len(unique_ids))) + 1
        curr_subject = 1

        for curr_id in unique_ids:
            mapping_df.ix[mapping_df['patient_id'] == curr_id, 'subject'] = 'sub-{}'.format(
                                                                                        str(curr_subject).rjust(
                                                                                            subject_padding, '0'))
            curr_subject += 1

            # Set the BIDS sessions based on datetime stamps of current subject
            unique_datetime = mapping_df[mapping_df['patient_id'] == curr_id]['scan_datetime'].unique()
            session_padding = len(str(len(unique_datetime))) + 1
            curr_session = 1

            for curr_datetime in unique_datetime:
                mapping_df.ix[(mapping_df['patient_id'] == curr_id) & (mapping_df['scan_datetime'] == curr_datetime),
                              'session'] = 'ses-{}'.format(str(curr_session).rjust(session_padding, '0'))
                curr_session += 1

                # Set the runs based on unique combinations of task/acq/rec/modality fields
                filtered_df = mapping_df.ix[(mapping_df['patient_id'] == curr_id) & (mapping_df['scan_datetime'] ==
                                                                                     curr_datetime)]
                unique_params = []
                for idx, row in filtered_df.iterrows():
                    curr_params = {
                        'task': row['task'],
                        'acq': row['acq'],
                        'rec': row['rec'],
                        'modality': row['modality'],
                    }
                    if curr_params not in unique_params:
                        unique_params.append(curr_params)

                for params in unique_params:
                    run_df = filtered_df.ix[(filtered_df['task'] == params['task']) &
                                            (filtered_df['acq'] == params['acq']) &
                                            (filtered_df['rec'] == params['rec']) &
                                            (filtered_df['modality'] == params['modality'])]
                    run_padding = len(str(len(run_df))) + 1
                    curr_run = 1
                    for idx, row in mapping_df.iterrows():
                        if row['patient_id'] == curr_id and row['scan_datetime'] == curr_datetime and \
                           row['task'] == params['task'] and row['acq'] == params['acq'] and \
                           row['rec'] == params['rec'] and row['modality'] == params['modality']:

                            row['run'] = "run-{}".format(str(curr_run).rjust(run_padding, '0'))
                            curr_run += 1
        mapping_df.sort_values(['subject', 'session', 'task', 'modality', 'run'],
                               ascending=['True', 'True', 'True', 'True', 'True'], inplace=True)

    return mapping_df


def main():

    start_datetime = get_datetime()

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "dicom_dir",
        help="Path to directory containing .tgz files from oxygen/gold",
    )

    parser.add_argument(
        "out_dir",
        help="Path to base output directory"
    )

    parser.add_argument(
        "--bids_map",
        help="Name for bids map.",
        default=None
    )

    parser.add_argument(
        "--biopac_dir",
        help="Path to directory containing biopac files.",
        default=None
    )

    # TODO: IMPLEMENT THIS
    parser.add_argument(
        "--overwrite",
        help="Overwrite existing files in BIDS data folder.",
        action="store_true",
        default=False
    )

    parser.add_argument(
        "--log",
        help="Log filename. Default will be oxy2bids_<timestamp>.log",
        default=None
    )

    parser.add_argument(
        "--nthreads",
        help="number of threads to use when running this script. Use 1 for sequential run.",
        default=get_cpu_count(),
        type=int
    )

    parser.add_argument(
        "--config",
        help="Custom config file",
        default=None
    )

    # TODO: Refactor some of the log msgs to only show up if this flag is set
    parser.add_argument(
        "--debug",
        help="Output debug statements",
        action='store_true',
        default=False
    )

    cli_args = parser.parse_args()

    out_dir = os.path.abspath(cli_args.out_dir)

    # Init Logger
    if cli_args.log:
        log_fpath = os.path.join(out_dir, cli_args.log)
    else:
        log_fpath = os.path.join(out_dir, "oxy2bids_{}.log".format(start_datetime))

    log = init_log(log_fpath, log_name='oxy2bids', debug=cli_args.debug)

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

    # Normalize directories
    dicom_dir = os.path.abspath(cli_args.dicom_dir)

    if cli_args.bids_dir:
        bids_dir = os.path.join(out_dir, cli_args.bids_dir)
    else:
        bids_dir = os.path.join(out_dir, "bids_data_{}".format(start_datetime))
        log.warning("A BIDS output directory was not specified!!! BIDS dataset will be stored in {}.".format(bids_dir))

    if cli_args.bids_map:
        bids_map = os.path.join(out_dir, cli_args.bids_map)
    else:
        bids_map = os.path.join(out_dir, "bids_map_{}.csv".format(start_datetime))
        log.warning("A DICOM to BIDS mapping was not provided... Will attempt to automatically generate one, and store"
                    " it in {}.".format(bids_map))

    biopac_dir = os.path.abspath(cli_args.biopac_dir) if cli_args.biopac_dir else None

    # Assign the rest of the settings to the settings variable
    settings["bids_map"] = bids_map
    settings["dicom_dir"] = dicom_dir
    settings["bids_dir"] = bids_dir
    settings["nthreads"] = cli_args.nthreads
    settings["biopac_dir"] = biopac_dir
    settings["overwrite"] = cli_args.overwrite

    log.info(json.dumps(settings, sort_keys=True, indent=2))

    settings["log"] = log

    # Generate Oxygen to BIDS mapping
    log.info(LOG_MESSAGES['start_map'])

    mapping = gen_map(settings)

    if mapping is not None:

        mapping.to_csv(path_or_buf=bids_map, index=False, header=True)
        log.info(LOG_MESSAGES['gen_map_done'].format(bids_map))

    else:

        log.warning(LOG_MESSAGES['map_failure'])

    # Shutdown the log
    log_shutdown(log)


if __name__ == "__main__":
    main()
