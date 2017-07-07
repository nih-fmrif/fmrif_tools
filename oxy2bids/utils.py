from __future__ import print_function, unicode_literals

import os
import re
import errno
import tarfile
import multiprocessing
import dicom
import logging
import json
import pkg_resources
import pandas as pd

from datetime import datetime
from glob import glob
from collections import OrderedDict

MAX_WORKERS = multiprocessing.cpu_count() * 5

date_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def init_log(log_fpath=None, debug=False):

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


def gen_map(dcm_dir, bids_map, custom_keys=None, ignore_default_tags=False, log=None, nthreads=0):

    default_keys = pkg_resources.resource_filename("oxy2bids", "data/bids_keys.json")

    log.info("Parsing BIDS key file...")

    if custom_keys:
        if ignore_default_tags:
            with open(custom_keys) as ckeys:
                bids_keys = json.load(ckeys)
        else:
            with open(default_keys) as dkeys:
                bids_keys = json.load(dkeys)
            with open(custom_keys) as ckeys:
                cust_keys = json.load(ckeys)

            for scan_type in bids_keys.keys():
                if cust_keys.get('scan_type', None):
                    bids_keys[scan_type].extend(cust_keys[scan_type])
    else:
        with open(default_keys) as dkeys:
            bids_keys = json.load(dkeys)

    log.info("BIDS key file parsed!")

    tgz_files = glob(os.path.join(dcm_dir, "*.tgz"))

    mapping_df = pd.DataFrame(columns=['subject', 'session', 'bids_type', 'task',
                                       'acq', 'rec', 'run', 'modality',
                                       'patient_id', 'scan_datetime', 'oxy_file',
                                       'scan_dir', 'resp_physio', 'cardiac_physio'])

    log.info("Parsing DICOM files...")

    for tgz_file in tgz_files:

        mr_folders_checked = []
        dicom_files = []
        realtime_files = []

        log.info("Parsing file {}...".format(tgz_file))

        tar = tarfile.open(tgz_file)
        tar_files = tar.getmembers()

        for tar_file in tar_files:

            tar_file_dir = "/".join(tar_file.name.split('/')[:-1])

            if tar_file.name[-4:] == ".dcm" and (tar_file_dir not in mr_folders_checked):
                dicom_files.append(tar_file.name)
                mr_folders_checked.append(tar_file_dir)

            if tar_file.name[-3:] == ".1D" and ("realtime" in tar_file.name):
                realtime_files.append(tar_file.name)

        for dcm_file in dicom_files:

            parse_results = parse_dicom(tar, dcm_file, realtime_files=realtime_files, bids_keys=bids_keys)

            if parse_results:
                tmp_df = pd.DataFrame.from_dict(parse_results)
                mapping_df = pd.concat([mapping_df, tmp_df], ignore_index=True)

        tar.close()

        log.info("Finished parsing {}!".format(tgz_file))

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
    mapping_df.to_csv(path_or_buf=bids_map, index=False, header=True,
                      columns=['subject', 'session', 'bids_type', 'task', 'acq', 'rec', 'run', 'modality',
                               'patient_id', 'scan_datetime', 'oxy_file', 'scan_dir', 'resp_physio', 'cardiac_physio'])


def extract_tgz(fpath, out_path=None, log=None):

    if not tarfile.is_tarfile(fpath):
        return fpath, False

    tar = tarfile.open(fpath, "r:gz")
    fname = fpath.split("/")[-1].split("-")
    scans_folder = os.path.join("{}-{}".format(fname[0], fname[1]), "{}-{}".format(fname[2], fname[3]))

    if not out_path:
        out_path = os.getcwd()
        extracted_dir = "{}".format(os.path.join(os.getcwd(), scans_folder))
    else:
        extracted_dir = "{}".format(os.path.join(out_path, scans_folder))

    tar.extractall(path=out_path)
    tar.close()

    if log:
        log.info("Extracted file {} to {} directory.".format(fpath, extracted_dir))

    return fpath, True


def parse_dicom(tar, dcm_file, bids_keys, realtime_files=None):

    curr_dcm = dicom.read_file(tar.extractfile(dcm_file))

    for bids_type in bids_keys.keys():

        tags = bids_keys[bids_type]

        # Iterate through the tags for the current bids type, see if they
        # match the current data in the specified dicom field

        for tag in tags:

            dicom_field = tag['dicom_field']

            dcm_dat = ""
            if dicom_field == 'series_description':
                dcm_dat = curr_dcm.SeriesDescription
            elif dicom_field == 'sequence_name':
                if curr_dcm.get((0x19, 0x109c), None):
                    dcm_dat = curr_dcm[0x19, 0x109c].value
                elif curr_dcm.get((0x18, 0x24), None):
                    dcm_dat = curr_dcm[0x18, 0x24].value
            else:
                raise Exception('Support for DICOM field {} not implemented.'.format(dicom_field))

            # No data was available for this tag
            if dcm_dat == "":
                continue

            # Verify that all the keywords in the include field are present
            match = True
            for expr in tag["include"]:
                pattern = r"(?:^|[ _]){}(?:[ _]|$)".format(expr)
                re_match = re.search(pattern, dcm_dat, re.IGNORECASE)
                if not re_match:
                    match = False
                    break

            if not match:
                continue

            # Verify that none of the keywords in the exclude field are present
            match = False
            for expr in tag["exclude"]:
                pattern = r"(?:^|[ _]){}(?:[ _]|$)".format(expr)
                re_match = re.search(pattern, dcm_dat, re.IGNORECASE)
                if re_match:
                    match = True
                    break

            if match:
                continue

            # Verify if there are task, acq, or rec pattern matches
            task = "task-NoTaskSpecified"
            if bids_type == "func":
                if tag.get("task_regexp", None):
                    pattern = tag["task_regexp"]
                    re_match = re.search(pattern, dcm_dat, re.IGNORECASE)
                    if re_match:
                        task = re_match.group(0).strip()
                elif tag.get("task_name", None):
                    task = tag["task_name"]

                # Todo: IMPLEMENT ENFORCEMENT OF EITHER OF THE TWO TASK SUBKEYS IN KEYFILE VALIDATOR

            acq = ""
            if tag.get("acq_regexp", None):
                pattern = tag["acq_regexp"]
                re_match = re.search(pattern, dcm_dat, re.IGNORECASE)
                if re_match:
                    acq = re_match.group(0).strip()
            elif tag.get("acq", None):
                acq = tag["aqc"]

            rec = ""
            if tag.get("rec_regexp", None):
                pattern = tag["rec_regexp"]
                re_match = re.search(pattern, dcm_dat, re.IGNORECASE)
                if re_match:
                    rec = re_match.group(0).strip()
            elif tag.get("rec", None):
                rec = tag["rec"]

            resp_physio = ""
            cardiac_physio = ""
            if realtime_files:
                for physio_dat in realtime_files:
                    curr_scan = dcm_file.split("/")[-2].split("_")[-1]
                    if "ECG" in physio_dat and \
                            ("scan_{}".format(curr_scan) in physio_dat):
                        cardiac_physio = physio_dat
                    elif "Resp" in physio_dat and \
                            ("scan_{}".format(curr_scan) in physio_dat):
                        resp_physio = physio_dat

            curr_map = OrderedDict({
                'subject': [""],
                'session': [""],
                'bids_type': [bids_type],
                'task': [task],
                'acq': [acq],
                'rec': [rec],
                'run': [""],
                'modality': [tag["bids_modality"]],
                'patient_id': [curr_dcm.PatientID],
                'scan_datetime': ["{}_{}".format(curr_dcm.StudyDate, curr_dcm.StudyTime)],
                'oxy_file': ["{}-DICOM.tgz".format("-".join(dcm_file.split("/")[:2]))],
                'scan_dir': [os.path.dirname(dcm_file)],
                'resp_physio': [resp_physio],
                'cardiac_physio': [cardiac_physio]
            })

            return curr_map

    return None
