from __future__ import print_function, unicode_literals

import os
import argparse
import logging
from converters import convert_to_bids
from utils import create_path, log_output, MAX_WORKERS, get_modality
from datetime import datetime


if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "bids_dir",
        help="Path to bids directory for output"
    )

    parser.add_argument(
        "dicom_dir",
        help="Path to bids directory for output"
    )

    parser.add_argument(
        "--subject_map",
        help="Path to the map of DICOM files to BIDS subjects",
        default=None
    )

    parser.add_argument(
        "--nthreads",
        help="number of threads to use when running this script. Use 0 for sequential run.",
        default=MAX_WORKERS,
        type=int
    )

    parser.add_argument(
        "--overwrite",
        help="Overwrite existing BIDS files.",
        action="store_true",
        default=False
    )

    parser.add_argument(
        "--log_dir",
        help="Path to directory where logs should be stored.",
        default=os.path.join(os.getcwd(), "logs")
    )

    settings = parser.parse_args()

    date_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    # Configure logger
    if not os.path.isdir(settings.log_dir):
        create_path(settings.log_dir)

    log_fname = "bids_conversion_{}.log".format(date_str)
    log_fpath = os.path.join(settings.log_dir, log_fname)

    # Remove all handlers associated with the root logger object.
    for handler in logging.root.handlers[:]:
        handler.close()
        logging.root.removeHandler(handler)

    logging.basicConfig(
        filename=log_fpath,
        level=logging.DEBUG,
        format='LOG ENTRY %(asctime)s - %(levelname)s \n%(message)s \nEND LOG ENTRY\n'
    )

    # Print the settings
    settings_str = "Bids directory: {}\n".format(settings.bids_dir) + \
                   "DICOM directory: {}\n".format(settings.dicom_dir) + \
                   "Subject map: {}\n".format(settings.subject_map) + \
                   "Overwrite: {}\n".format(settings.overwrite) + \
                   "Log directory: {}\n".format(settings.log_dir) + \
                   "Number of threads: {}".format(settings.nthreads)

    log_output(settings_str, logger=logging)

    log_output("Beginning conversion to BIDS format.\n"
               "Log located in {}.".format(log_fpath), logger=logging)

    # Use the subject map to convert the DICOM series into BIDS-structured Nifti files
    convert_to_bids(bids_dir=settings.bids_dir, dicom_dir=settings.dicom_dir, subject_map=settings.subject_map,
                    conversion_tool='dcm2niix', logger=logging, nthreads=settings.nthreads,
                    overwrite=settings.overwrite)

    log_output("BIDS conversion complete. Results stored in {} directory".format(settings.bids_dir), logger=logging)

    # Remove all handlers associated with the root logger object.
    for handler in logging.root.handlers[:]:
        handler.close()
        logging.root.removeHandler(handler)
