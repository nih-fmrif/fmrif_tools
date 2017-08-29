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

from common_utils.utils import init_log, log_shutdown, create_path
from datetime import datetime


def biounpacker(biopac_file):

    data = bioread.read_file(biopac_file)

    biopac_channels = {
        'resp': data.channels[0],
        'ecg': data.channels[1],
        'triggers': data.channels[2]
    }

    return biopac_channels


if __name__ == "__main__":

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
        help='Labeling prefix for output',
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
    log = init_log(log_fpath, log_name='biounpack')

    log.info("Reading biopack file: {}".format(settings.input_file))

    biopac_channels = biounpacker(settings.input_file)

    data_resp = np.array(biopac_channels['resp'].data, dtype=float)
    data_ecg = np.array(biopac_channels['ecg'].data, dtype=float)
    data_trigger = np.array(biopac_channels['triggers'].data, dtype=float)

    if settings.info:
        log.info("Plotting physiological data onto file: "
                 "{}_plots.pdf".format(settings.output_prefix))

        fig = plt.figure()
        fig.set_size_inches(8.5, 11)
        fig.subplots_adjust(hspace=3, wspace=0)
        plt.subplot(3, 1, 1)
        plt.title("{} - {} samples/secs".format(biopac_channels['resp'].name,
                                                biopac_channels['resp'].samples_per_second))
        plt.ylabel(biopac_channels['resp'].units)
        plt.xlabel("sample")
        plt.plot(data_resp)
        plt.subplot(3, 1, 2)
        plt.title("{} - {} samples/secs".format(biopac_channels['ecg'].name,
                                                biopac_channels['ecg'].samples_per_second))
        plt.ylabel(biopac_channels['ecg'].units)
        plt.xlabel("sample")
        plt.plot(data_ecg)
        plt.subplot(3, 1, 3)
        plt.title("{} - {} samples/secs".format(biopac_channels['triggers'].name,
                                                biopac_channels['triggers'].samples_per_second))
        plt.ylabel(biopac_channels['triggers'].units)
        plt.xlabel("sample")
        plt.plot(data_trigger)
        fig.tight_layout()
        plt.savefig("{}_plots.pdf".format(settings.output_prefix))
        plt.close()

    out_path = os.path.abspath(settings.output_prefix)

    if not os.path.isdir(os.path.dirname(out_path)):
        log.info("Creating output directory: {}".format(os.path.dirname(out_path)))
        create_path(os.path.dirname(out_path))

    log.info("Saving 1D files...")

    np.savetxt(out_path + '_Resp.1D', data_resp)
    np.savetxt(out_path + '_ECG.1D', data_ecg)
    np.savetxt(out_path + '_Trigger.1D', data_trigger)

    log.info("Biopack data to 1D file conversion complete!")

    log_shutdown(log)
