#!/usr/bin/env python
# @Author: Benjamin E. Gutierrez, Dan Handwerker
# @Date:   2016-05-03
# @Last Modified by: Jan Varada
# @Last Modified time: 2017-06-13 16:17

"""
This script takes a Biopac input file and outputs the file data in a 1D form.
"""

import numpy as np
import argparse
import os
import bioread
import matplotlib.pyplot as plt

from datetime import datetime
from oxy2bids.utils import init_log, log_shutdown, create_path


def main():

    parser = argparse.ArgumentParser('Options')

    parser.add_argument(
        '-i',
        dest="input_file",
        help='Input file from Biopac',
        type=str,
        required=True
    )

    parser.add_argument(
        '-o',
        dest="output_prefix",
        help='Output directory, including desired file prefix. '
             'If only a prefix is provided, the output directory '
             'will be the current working directory',
        type=str,
        required=True,
    )

    parser.add_argument(
        '--overwrite',
        dest="overwrite",
        help='Overwrite output files',
        default=False,
        action='store_true'
    )

    parser.add_argument(
        '--info',
        dest="info",
        help='Output info and plots',
        default=True,
        action='store_true'
    )

    settings = parser.parse_args()

    if os.path.isfile(settings.output_prefix + "_ECG.1D") and not settings.overwrite:
        parser.error("++ Error: Output file already exists and overwrite flag not given.")

    # Initiate log
    start_datetime = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    log_fpath = os.path.join(os.getcwd(), "biounpack_{}.log".format(start_datetime))
    log = init_log(log_fpath)

    output_prefix = os.path.abspath(settings.output_prefix)

    log.info("Reading biopack file: {}".format(settings.input_file))

    data = bioread.read_file(settings.input_file)

    log.info("Parsing biopack file...")

    data_resp = np.array(data.channels[0].data, dtype=float)
    data_ecg = np.array(data.channels[1].data, dtype=float)
    data_trigger = np.array(data.channels[2].data, dtype=float)

    if settings.info:

        log.info("Plotting physiological data onto file: "
                 "{}_plots.pdf".format(settings.output_prefix))

        fig = plt.figure()
        fig.set_size_inches(8.5, 11)
        fig.subplots_adjust(hspace=3, wspace=0)
        plt.subplot(3, 1, 1)
        plt.title("{} - {} samples/secs".format(data.channels[0].name, data.channels[0].samples_per_second))
        plt.ylabel(data.channels[0].units)
        plt.xlabel("sample")
        plt.plot(data_resp)
        plt.subplot(3, 1, 2)
        plt.title("{} - {} samples/secs".format(data.channels[1].name, data.channels[1].samples_per_second))
        plt.ylabel(data.channels[0].units)
        plt.xlabel("sample")
        plt.plot(data_ecg)
        plt.subplot(3, 1, 3)
        plt.title("{} - {} samples/secs".format(data.channels[2].name, data.channels[2].samples_per_second))
        plt.ylabel(data.channels[2].units)
        plt.xlabel("sample")
        plt.plot(data_trigger)
        fig.tight_layout()
        plt.savefig("{}_plots.pdf".format(settings.output_prefix))
        plt.close()

    output_dir = os.path.dirname(output_prefix)

    # Check whether the files that will be created already exist,
    # throw error and abort if they exist and --overwrite flag
    # not present
    resp_fpath = os.path.join(output_prefix, "_Resp.1D")
    ecg_fpath = os.path.join(output_prefix, "_ECG.1D")
    trigger_fpath = os.path.join(output_prefix, "_Trigger.1D")

    if not settings.overwrite:
        err = False
        err_msg = "Output file {} already exists, and --overwrite flag is not present."
        if os.path.isfile(resp_fpath):
            log.error(err_msg.format(resp_fpath))
            err = True
        if os.path.isfile(ecg_fpath):
            log.error(err_msg.format(ecg_fpath))
            err = True
        if os.path.isfile(trigger_fpath):
            log.error(err_msg.format(ecg_fpath))
            err = True
        if err:
            log.error("Aborting...")
            return

    if not os.path.isdir(output_dir):
        log.info("Creating output directory: {}".format(output_dir))
        create_path(output_dir)

    log.info("Saving 1D files...")

    np.savetxt(settings.output_prefix + '_Resp.1D', data_resp)
    np.savetxt(settings.output_prefix + '_ECG.1D', data_ecg)
    np.savetxt(settings.output_prefix + '_Trigger.1D', data_trigger)

    log.info("Biopac data to 1D file conversion complete!")

    log_shutdown(log)


if __name__ == "__main__":
    main()
