from __future__ import print_function, unicode_literals

import os
import argparse

from oxy2bids.converters import process_bids_map
from oxy2bids.utils import init_log, log_shutdown, gen_map, MAX_WORKERS
from datetime import datetime


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "dicom_dir",
        help="Path to directory containing .tgz files from oxygen",
    )

    parser.add_argument(
        "--auto",
        help="Automatically generate BIDS data from DICOM data based on best-guessed mapping. Default: False.",
        action='store_true',
        default=False,
    )

    parser.add_argument(
        "--gen_map",
        help="Create initial DICOM to BIDS map, to be verified and fined tuned as desired before conversion. "
             " Default: True",
        action='store_true',
        default=True
    )

    parser.add_argument(
        "--bids_dir",
        help="Path to desired top-level output directory of BIDS-formatted dataset. If not specified, a directory named"
             " bids_data_<timestamp> in the current working directory will be created.",
        default=None
    )

    parser.add_argument(
        "--bids_map",
        help="Path to a preexisting DICOM to BIDS mapping. Overrides --gen_map flag.",
        default=None
    )

    parser.add_argument(
        "--dicom_tags",
        help="Path to a DICOM header tag specification file.",
        default=None
    )

    parser.add_argument(
        "--ignore_default_tags",
        help="Ignore the default BIDS tags if custom tags if custom tags are "
             "provided with the --dicom_tags flags. Otherwise the custom tags "
             "are considered on top of the default ones.",
        default=False
    )

    parser.add_argument(
        "--conversion_tool",
        help="Tool to convert DICOM scans to NIFTI files. Options: dcm2niix (default), dimon.",
        default='dcm2niix'
    )

    parser.add_argument(
        "--overwrite",
        help="Overwrite existing files in BIDS data folder.",
        action="store_true",
        default=False
    )

    parser.add_argument(
        "--log",
        help="Log filepath. Default will be oxy2bids_<timestamp>.log in current working directory.",
        default=None
    )

    parser.add_argument(
        "--nthreads",
        help="number of threads to use when running this script. Use 0 for sequential run.",
        default=MAX_WORKERS,
        type=int
    )

    parser.add_argument(
        "--debug",
        help="Output debug statements",
        action='store_true',
        default=False
    )

    settings = parser.parse_args()

    if not settings.auto and not settings.gen_map and not settings.bids_map:
        parser.error("If the --auto or --gen_map flags are not specified, a DICOM to BIDS map "
                     "must be provided via the --bids_map flag.")

    if settings.auto and settings.bids_map:
        parser.error("Specify either a bids map (--bids_map) or enable automatic conversion mode (--auto) but "
                     " not both.")

    if settings.ignore_default_tags and not settings.dicom_tags:
        parser.error("If the --ignore_default_tags is set to True, you must provide a "
                     "custom tags file via the --dicom_tags flag.")

    start_datetime = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")

    # Init default files/directories and/or normalized user provided filepaths/directories
    dicom_dir = os.path.abspath(settings.dicom_dir)

    if not settings.bids_dir:
        bids_dir = os.path.join(os.getcwd(), "bids_data_{}".format(start_datetime))
    else:
        bids_dir = os.path.abspath(settings.bids_dir)

    if settings.bids_map:
        bids_map = os.path.abspath(settings.bids_map)
    else:
        bids_map = os.path.join(os.getcwd(), "bids_map_{}.csv".format(start_datetime))

    if settings.log:
        log_fpath = os.path.abspath(settings.log)
    else:
        log_fpath = os.path.join(os.getcwd(), "oxy2bids_{}.log".format(start_datetime))

    if settings.dicom_tags:
        custom_keys = os.path.abspath(settings.dicom_tags)
    else:
        custom_keys = None

    # Init logger
    log = init_log(log_fpath, settings.debug)

    # Print the settings
    settings_str = "DICOM directory: {}\n".format(dicom_dir) + \
                   "Generate map: {}\n".format(settings.gen_map) + \
                   "Bids directory: {}\n".format(bids_dir) + \
                   "BIDS map: {}\n".format(bids_map) + \
                   "Automatic analysis: {}\n".format(settings.auto) +\
                   "DICOM tags file: {}\n".format("default" if not custom_keys else custom_keys) +\
                   "Ignore default DICOM tags: {}\n".format(settings.ignore_default_tags) +\
                   "Conversion tool: {}\n".format(settings.conversion_tool) + \
                   "Overwrite: {}\n".format(settings.overwrite) + \
                   "Log: {}\n".format(log_fpath) + \
                   "Number of threads: {}".format(settings.nthreads)

    # Main log messages
    LOG_MESSAGES = {
        'start_conversion': "Beginning conversion to BIDS format",
        'start_map': "Beginning generation of DICOM to BIDS map.",
        'gen_map_warning': "WARNING: --gen_map and --bids_map flags specified. Will use existing bids map instead of "
                           "generating one.",
        'gen_map_done': "Map generation complete. Results stored in {}".format(bids_map),
        'shutdown': "BIDS conversion complete. Results stored in {}".format(bids_dir)
    }

    log.info(settings_str)

    if settings.auto:

        # Generate Oxygen to BIDS mapping
        log.info(LOG_MESSAGES['start_map'])
        gen_map(dicom_dir, bids_map=bids_map, custom_keys=custom_keys, ignore_default_tags=settings.ignore_default_tags,
                log=log, nthreads=settings.nthreads)
        log.info(LOG_MESSAGES['gen_map_done'])

        # Use generated map to convert files
        log.info(LOG_MESSAGES['start_conversion'])
        process_bids_map(bids_map=bids_map, bids_dir=bids_dir, dicom_dir=dicom_dir, conversion_tool='dcm2niix', log=log,
                         start_datetime=start_datetime, nthreads=settings.nthreads)
        log.info(LOG_MESSAGES['shutdown'])

    elif settings.bids_map:

        # Use provided map to convert files
        log.info(LOG_MESSAGES['start_conversion'])
        process_bids_map(bids_map=bids_map, bids_dir=bids_dir, dicom_dir=dicom_dir, conversion_tool='dcm2niix', log=log,
                         start_datetime=start_datetime, nthreads=settings.nthreads)
        log.info(LOG_MESSAGES['shutdown'])

    elif settings.gen_map:

        # Generate Oxygen to BIDS mapping
        log.info(LOG_MESSAGES['start_map'])
        gen_map(dicom_dir, bids_map=bids_map, custom_keys=custom_keys, ignore_default_tags=settings.ignore_default_tags,
                log=log, nthreads=settings.nthreads)
        log.info(LOG_MESSAGES['gen_map_done'])

    # Shutdown the log
    log_shutdown(log)


if __name__ == "__main__":
    main()
