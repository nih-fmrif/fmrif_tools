from __future__ import print_function, unicode_literals

import os
import argparse
import json

from pathlib import Path
from oxy2bids.constants import LOG_MESSAGES
from common_utils.utils import init_log, log_shutdown, get_cpu_count, get_datetime, get_config
from oxy2bids.converters import BIDSConverter
from bidsmapper.mapper import gen_map


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
        "--bids_dir",
        help="Name for top-level output of BIDS-formatted dataset. If not specified, a directory named"
             " bids_data_<timestamp> will be created",
        default=None
    )

    parser.add_argument(
        "--bids_map",
        help="Filepath of pre-existing DICOM to BIDS mapping",
        default=None
    )

    parser.add_argument(
        "--biopac_dir",
        help="Path to directory containing biopac files",
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

    settings = {}

    cli_args = parser.parse_args()

    settings["debug"] = cli_args.debug

    print(Path(cli_args.out_dir))

    settings["out_dir"] = Path(cli_args.out_dir).absolute()

    # Init log
    log_fpath = settings["out_dir"] / "oxy2bids_{}.log".format(start_datetime)

    print(log_fpath)

    settings["log"] = init_log(log_fpath, log_name='oxy2bids', debug=settings["debug"])

    # Load config file
    settings["config"] = get_config(cli_args.config)

    # Normalize directories
    settings["dicom_dir"] = Path(cli_args.dicom_dir).absolute()

    if cli_args.bids_dir:

        settings['bids_dir'] = Path(cli_args.bids_dir).absolute()

        if not settings['bids_dir'].is_dir():
            settings['log'].error("BIDS directory {} not found. Aborting...".format(cli_args.bids_dir))

    else:

        settings["bids_dir"] = settings["out_dir"] / "bids_data_{}".format(start_datetime)

        settings["log"].warning("A BIDS output directory was not specified!!! "
                                "BIDS dataset will be stored in {}.".format(settings["bids_dir"]))

    valid_bmap = False

    if cli_args.bids_map:

        settings['bids_map'] = Path(cli_args.bids_map).absolute()

        if settings['bids_map'].is_file():
            valid_bmap = True
        else:
            settings["log"].error("DICOM to BIDS map {} not found. Aborting...".format(cli_args.bids_map))
            return
    else:

        settings["bids_map"] = settings["out_dir"] / "bids_map_{}.csv".format(start_datetime)

        settings["log"].warning("A DICOM to BIDS mapping was not provided... Will attempt to automatically "
                                "generate one, and store it in {}.".format(settings["bids_map"]))

    settings["biopac_dir"] = Path(cli_args.biopac_dir).absolute() if cli_args.biopac_dir else None

    settings["nthreads"] = cli_args.nthreads

    settings["overwrite"] = cli_args.overwrite

    # Print the settings
    settings["log"].info(json.dumps({key: settings[key] for key in settings if key != 'log'}, sort_keys=True,
                                    indent=2))

    converter = BIDSConverter(conversion_tool='dcm2niix', log=settings["log"])

    if valid_bmap:

        # Use provided map to convert files
        settings["log"].info(LOG_MESSAGES['start_conversion'])

        converter.map_to_bids(
            bids_map=str(settings["bids_map"]),
            bids_dir=str(settings["bids_dir"]),
            dicom_dir=str(settings["dicom_dir"]),
            biopac_dir=str(settings["biopac_dir"]),
            nthreads=settings["nthreads"],
            overwrite=settings["overwrite"]
        )

        settings["log"].info(LOG_MESSAGES['shutdown'].format(settings["bids_dir"]))

    else:

        # Generate Oxygen to BIDS mapping
        settings["log"].info(LOG_MESSAGES['start_map'])

        mapping = gen_map(
            dicom_dir=str(settings["dicom_dir"]),
            bids_tags=settings["config"]["BIDS_TAGS"],
            dicom_tags=settings["config"]["DICOM_TAGS"],
            nthreads=settings["nthreads"],
            log=settings["log"]
        )

        if mapping is not None:

            col_order = ['subject', 'session', 'bids_type', 'task', 'acq', 'rec', 'run', 'modality', 'patient_id',
                         'scan_datetime', 'scan_dir', 'resp_physio', 'cardiac_physio', 'biopac']

            # Save map to csv
            mapping.to_csv(
                path_or_buf=str(settings["bids_map"]),
                index=False,
                header=True,
                columns=col_order
            )
            settings["log"].info(LOG_MESSAGES['gen_map_done'].format(settings["bids_map"]))

            # Use generated map to convert files
            settings["log"].info(LOG_MESSAGES['start_conversion'])

            converter.map_to_bids(
                bids_map=str(settings["bids_map"]),
                bids_dir=str(settings["bids_dir"]),
                dicom_dir=str(settings["dicom_dir"]),
                biopac_dir=str(settings["biopac_dir"]),
                nthreads=settings["nthreads"],
                overwrite=settings["overwrite"]
            )

            settings["log"].info(LOG_MESSAGES['shutdown'].format(settings["bids_dir"]))

        else:

            settings["log"].warning("A mapping could not be generated. See log for details.")

    # Shutdown the log
    log_shutdown(settings["log"])


if __name__ == "__main__":
    main()
