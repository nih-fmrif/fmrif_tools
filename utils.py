from __future__ import print_function, unicode_literals

import os
import errno
import multiprocessing
import logging

from datetime import datetime


def get_datetime():
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def get_cpu_count():
    return multiprocessing.cpu_count()


def init_log(log_fpath=None, log_name=None, debug=False):

    if log_name:
        log = logging.getLogger(log_name)
    else:
        log = logging.getLogger('oxy2bids')

    if debug:
        log.setLevel(logging.DEBUG)
    else:
        log.setLevel(logging.INFO)

    # Log formatter
    log_fmt = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Log Handler for console
    console_handler = logging.StreamHandler()
    if debug:
        console_handler.setLevel(logging.DEBUG)
    else:
        console_handler.setLevel(logging.INFO)

    console_handler.setFormatter(log_fmt)
    log.addHandler(console_handler)

    if log_fpath:
        # Log handler for file
        file_handler = logging.FileHandler(log_fpath)
        if debug:
            file_handler.setLevel(logging.DEBUG)
        else:
            file_handler.setLevel(logging.INFO)

        file_handler.setFormatter(log_fmt)
        log.addHandler(file_handler)

    return log


def log_shutdown(log):
    logging.shutdown()
    del log


def create_path(path, semaphore=None):

    if semaphore:
        semaphore.acquire()

    try:
        os.makedirs(path)
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise

    if semaphore:
        semaphore.release()
