from __future__ import print_function, unicode_literals

import os
import re
import errno
import tarfile
import multiprocessing
import dicom
import logging
import json
import pandas as pd

from datetime import datetime
from glob import glob

MAX_WORKERS = multiprocessing.cpu_count() * 5

date_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def init_log(log_fpath, debug=False):

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
    log.shutdown()


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


def gen_map(dcm_dir, bids_map, custom_keys=None, log=None, nthreads=0):

    if custom_keys:
        key_file = custom_keys
    else:
        key_file = "bids_keys.json"

    with open(key_file) as f:
        bids_keys = json.load(f)

    tgz_files = glob(os.path.join(dcm_dir, "*.tgz"))

    mapping_df = pd.DataFrame(columns=['subject', 'session', 'bids_type', 'task',
                                       'acq', 'rec', 'run', 'modality',
                                       'patient_id', 'scan_datetime', 'oxy_file',
                                       'scan_dir', 'resp_physio', 'cardio_physio'])

    for tgz_file in tgz_files:

        mr_folders_checked = []
        dicom_files = []
        realtime_files = []

        tar = tarfile.open(tgz_file)
        tar_files = tar.getmembers()

        for tar_file in tar_files:

            split_name = tar_file.name.split('/')
            tar_file_dir = "/".join(split_name[:3])

            if len(split_name) == 4 and ".dcm" in split_name[-1] and 'mr_' in split_name[-2] and \
               (tar_file_dir not in mr_folders_checked):

                dicom_files.append(tar_file.name)
                mr_folders_checked.append(tar_file_dir)

            if len(split_name) == 4 and (".1D" in split_name[-1]) and (split_name[-2] == "realtime"):
                realtime_files.append(tar_file.name)

        for dcm_file in dicom_files:

            parse_results = parse_dicom(tar, dcm_file, realtime_files=realtime_files, bids_keys=bids_keys)

            if parse_results:
                tmp_df = pd.DataFrame.from_dict(parse_results)
                mapping_df = pd.concat([mapping_df, tmp_df], ignore_index=True)

        tar.close()

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
                print(mapping_df)

    mapping_df.to_csv(path_or_buf=bids_map, index=False)


def extract_tgz(fpath, out_path='.', logger=None, semaphore=None):

    if not tarfile.is_tarfile(fpath):
        raise tarfile.TarError("{} is not a valid tar/gzip file.".format(fpath))

    tar = tarfile.open(fpath, "r:gz")
    # scans_folder = tar.next().name
    fname = fpath.split("/")[-1].split("-")
    scans_folder = os.path.join("{}-{}".format(fname[0], fname[1]), "{}-{}".format(fname[2], fname[3]))
    tar.extractall(path=out_path)
    tar.close()

    extracted_dir = "{}"

    if out_path == ".":
        extracted_dir = extracted_dir.format(os.path.join(os.getcwd(), scans_folder))
    else:
        extracted_dir = extracted_dir.format(os.path.join(out_path, scans_folder))

    log_output("Extracted file {} to {} directory.".format(fpath, extracted_dir), logger=logger, semaphore=semaphore)

    return extracted_dir


def parse_dicom(tar, dcm_file, bids_keys, realtime_files=None):

    curr_dcm = dicom.read_file(tar.extractfile(dcm_file))

    for bids_type in bids_keys.keys():

        tags = bids_keys[bids_type]

        # Iterate through the tags for the current bids type, see if they
        # match the current data in the specified dicom field

        for tag in tags:

            dicom_field = tag['dicom_field']

            if dicom_field == 'series_description':
                dcm_dat = curr_dcm.SeriesDescription
            elif dicom_field == 'pulse_seq_name':
                dcm_dat = curr_dcm[0x19,0x109c].value
            else:
                raise Exception('Support for DICOM field {} not implemented.'.format(dicom_field))

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
            task = ""
            if bids_type == "func":
                pattern = tag["task_regexp"]
                re_match = re.search(pattern, dcm_dat, re.IGNORECASE)
                if re_match:
                    task = re_match.group(0).strip()
                else:
                    task = "notaskspecified"

            acq = ""
            pattern = tag["acq_regexp"]
            re_match = re.search(pattern, dcm_dat, re.IGNORECASE)
            if re_match:
                acq = re_match.group(0).strip()

            rec = ""
            if tag.get("rec_regexp", None):
                pattern = tag["rec_regexp"]
                re_match = re.search(pattern, dcm_dat, re.IGNORECASE)
                if re_match:
                    rec = re_match.group(0).strip()

            resp_physio = ""
            cardio_physio = ""
            if realtime_files:
                for item in enumerate(realtime_files):
                    if "ECG" in item and ("scan_{}".format(dcm_file.split("/")[-2].split("_")[-1] in item)):
                        cardio_physio = item
                    elif "Resp" in item and ("scan_{}".format(dcm_file.split("/")[-2].split("_")[-1] in item)):
                        resp_physio = item

            curr_map = {
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
                'scan_dir': [dcm_file],
                'resp_physio': [resp_physio],
                'cardio_physio': [cardio_physio]
            }

            return curr_map

    return None
