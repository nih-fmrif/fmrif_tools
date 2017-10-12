from __future__ import print_function, unicode_literals

import os
import argparse
import json

from oxy2bids.constants import LOG_MESSAGES
from common_utils.config import get_config
from common_utils.utils import init_log, log_shutdown, get_cpu_count, get_datetime
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
             " bids_data_<timestamp> will be created.",
        default=None
    )

    parser.add_argument(
        "--bids_map",
        help="Filepath of pre-existing DICOM to BIDS mapping. If the file specified does not exist, will "
             "use the provided filename to name an automatically created mapping.",
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
            custom_config = json.load(os.path.abspath(cli_args.config))
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

    valid_bmap = False
    if cli_args.bids_map:

        if not os.path.isfile(os.path.abspath(cli_args.bids_map)):
            log.warning("{} not found. Using {} as DICOM to BIDS map name.".format(cli_args.bids_map,
                                                                                   os.path.basename(cli_args.bids_map)))
            map_bname = os.path.basename(cli_args.bids_map)

            if map_bname.endswith(".csv"):
                bids_map = os.path.join(out_dir, map_bname)
            else:
                bids_map = os.path.join(out_dir, "{}.csv".format(map_bname))
        else:
            bids_map = os.path.abspath(cli_args.bids_map)
            valid_bmap = True

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

    # Print the settings
    log.info(json.dumps(settings, sort_keys=True, indent=2))

    settings["log"] = log

    converter = BIDSConverter(conversion_tool='dcm2niix', log=log)

    if valid_bmap:

        # Use provided map to convert files
        log.info(LOG_MESSAGES['start_conversion'])

        converter.map_to_bids(settings=settings)

        log.info(LOG_MESSAGES['shutdown'].format(bids_dir))

    else:

        # Generate Oxygen to BIDS mapping
        log.info(LOG_MESSAGES['start_map'])

        mapping = gen_map(settings=settings)

        if mapping is not None:

            # Save map to csv
            mapping.to_csv(path_or_buf=bids_map, index=False, header=True)
            log.info(LOG_MESSAGES['gen_map_done'].format(bids_map))

            # Use generated map to convert files
            log.info(LOG_MESSAGES['start_conversion'])

            converter.map_to_bids(settings=settings)

            log.info(LOG_MESSAGES['shutdown'].format(bids_dir))

        else:

            log.warning("A mapping could not be generated. See log for details.")

    # Shutdown the log
    log_shutdown(log)


if __name__ == "__main__":
    main()
