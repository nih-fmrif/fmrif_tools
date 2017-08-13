from __future__ import print_function, unicode_literals

import os
import argparse
import json

from common_utils.utils import init_log, log_shutdown, get_cpu_count, get_datetime
from oxy2bids.converters import process_bids_map
from bidsmapper.mapper import gen_map

# Main log messages
LOG_MESSAGES = {
    'start_conversion': "Beginning conversion to BIDS format",
    'start_map': "Beginning generation of DICOM to BIDS map.",
    'gen_map_warning': "WARNING: --gen_map and --bids_map flags specified. Will use existing bids map instead of "
                       "generating one.",
    'gen_map_done': "Map generation complete. Results stored in {}",
    'shutdown': "BIDS conversion complete. Results stored in {}"
}


def main():

    start_datetime = get_datetime()

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "dicom_dir",
        help="Path to directory containing .tgz files from oxygen",
    )

    parser.add_argument(
        "--bids_dir",
        help="Path to desired top-level output directory of BIDS-formatted dataset. If not specified, a directory named"
             " bids_data_<timestamp> in the current working directory will be created.",
        default=None
    )

    parser.add_argument(
        "--bids_map",
        help="Path to a preexisting DICOM to BIDS mapping.",
        default=None
    )

    parser.add_argument(
        "--heuristics",
        help="Path to a heuristics specification file.",
        default=None
    )

    parser.add_argument(
        "--dicom_tags",
        help="Path to a DICOM header tag specification file.",
        default=None
    )

    parser.add_argument(
        "--overwrite",
        help="Overwrite existing files in BIDS data folder.",
        action="store_true",
        default=False
    )

    parser.add_argument(
        "--log",
        help="Log filename. Default will be oxy2bids_<timestamp>.log in current working directory.",
        default=None
    )

    parser.add_argument(
        "--nthreads",
        help="number of threads to use when running this script. Use 1 for sequential run.",
        default=get_cpu_count(),
        type=int
    )

    # TODO: Refactor some of the log msgs to only show up if this flag is set
    parser.add_argument(
        "--debug",
        help="Output debug statements",
        action='store_true',
        default=False
    )

    settings = parser.parse_args()

    # Init logger
    if settings.log:
        log_name = os.path.abspath(settings.log)
    else:
        log_name = os.path.join(os.getcwd(), "oxy2bids_{}.log".format(start_datetime))

    log = init_log(log_name, settings.debug)

    # Normalize directories
    dicom_dir = os.path.abspath(settings.dicom_dir)

    if settings.bids_dir:
        bids_dir = os.path.abspath(settings.bids_dir)
    else:
        bids_dir = os.path.join(os.getcwd(), "bids_data_{}".format(start_datetime))
        log.warning("A BIDS output directory was not specified... Will store BIDS results in {}.".format(bids_dir))

    if settings.bids_map:
        bids_map = os.path.abspath(settings.bids_map)
    else:
        bids_map = os.path.join(os.getcwd(), "bids_map_{}.csv".format(start_datetime))
        log.warning("A DICOM to BIDS mapping was not provided... Will attempt to automatically generate one, and store"
                    "it in {}.".format(bids_map))

    heuristics = os.path.abspath(settings.heuristics) if settings.heuristics else None

    # Print the settings
    curr_settings = {
        "DICOM Directory": dicom_dir,
        "BIDS Directory": bids_dir,
        "BIDS map": bids_map,
        "Overwrite": settings.overwrite,
        "Log": log_name,
        "Number of threads": settings.nthreads
        # "DICOM tags file: {}\n".format("default" if not custom_keys else custom_keys) + \
    }

    log.info(json.dumps(curr_settings, sort_keys=True, indent=2))

    if settings.bids_map:

        # Use provided map to convert files
        log.info(LOG_MESSAGES['start_conversion'])

        process_bids_map(bids_map=bids_map, bids_dir=bids_dir, dicom_dir=dicom_dir, conversion_tool='dcm2niix', log=log,
                         start_datetime=start_datetime, nthreads=settings.nthreads)

        log.info(LOG_MESSAGES['shutdown'].format(bids_dir))

    else:

        # Generate Oxygen to BIDS mapping
        log.info(LOG_MESSAGES['start_map'])

        mapping = gen_map(dicom_dir=dicom_dir, heuristics=heuristics, nthreads=settings.nthreads, log=log)

        if mapping is not None:

            # Save map to csv
            mapping.to_csv(path_or_buf=bids_map, index=False, header=True)
            log.info(LOG_MESSAGES['gen_map_done'].format(bids_map))

            # Use generated map to convert files
            log.info(LOG_MESSAGES['start_conversion'])

            process_bids_map(bids_map=bids_map, bids_dir=bids_dir, dicom_dir=dicom_dir, conversion_tool='dcm2niix',
                             log=log, start_datetime=start_datetime, nthreads=settings.nthreads)

            log.info(LOG_MESSAGES['shutdown'])

        else:

            log.warning("A mapping could not be generated. See log for details.")

    # Shutdown the log
    log_shutdown(log)


if __name__ == "__main__":
    main()
