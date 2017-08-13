from __future__ import print_function, unicode_literals

import os
import re
import io
import dicom

from collections import OrderedDict
from subprocess import CalledProcessError, check_output, STDOUT


class DicomScan:

    def __init__(self, scan_path, dicom_dir, compressed=True, cardio=None, resp=None, triggers=None):
        self._scan_path = scan_path
        self._dicom_dir = dicom_dir
        self._cardio = cardio
        self._resp = resp
        self._triggers = triggers
        self._compressed = compressed

    def get_scan_path(self):
        return self._scan_path

    def get_scan_dir(self):
        return os.path.dirname(self._scan_path)

    def get_scan_name(self):
        return os.path.basename(self._scan_path)

    def get_dicom_dir(self):
        return os.path.abspath(self._dicom_dir)

    def get_cardio(self):
        return self._cardio

    def get_resp(self):
        return self._resp

    def get_triggers(self):
        return self._triggers

    def is_compressed(self):
        return self._compressed

    def set_cardio(self, cardio):
        self._cardio = cardio

    def set_resp(self, resp):
        self._resp = resp

    def set_triggers(self, triggers):
        self._triggers = triggers

    def set_compressed(self, compressed):
        self._compressed = compressed


def dicom_parser(scan, heuristics, log=None):

    dcm_file = scan.get_scan_path()

    if scan.is_compressed():

        scan_subject, scan_session, _ = scan.get_scan_dir().split("/")

        compressed_file = os.path.join(scan.get_dicom_dir(), "{}-{}-DICOM.tgz".format(scan_subject, scan_session))

        try:

            oxy_bytes = check_output('tar -O -xf {} {}'.format(compressed_file, dcm_file),
                                     shell=True, stderr=STDOUT)

        except CalledProcessError:

            log.error("Unable to extract {} from {}".format(dcm_file, compressed_file))
            raise Exception("An error has occurred. Check log for details.")

        oxy_fobj = io.BytesIO(oxy_bytes)

        curr_dcm = dicom.read_file(oxy_fobj, stop_before_pixels=True)

    else:

        curr_dcm = dicom.read_file(dcm_file, stop_before_pixels=True)

    for heuristic in heuristics.keys():

        tags = heuristics[heuristic]

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
                pattern = r"(?:^|[ _-]){}(?:[ _-]|$)".format(expr)
                re_match = re.search(pattern, dcm_dat, re.IGNORECASE)
                if not re_match:
                    match = False
                    break

            if not match:
                continue

            # Verify that none of the keywords in the exclude field are present
            match = False
            for expr in tag["exclude"]:
                pattern = r"(?:^|[ _-]){}(?:[ _-]|$)".format(expr)
                re_match = re.search(pattern, dcm_dat, re.IGNORECASE)
                if re_match:
                    match = True
                    break

            if match:
                continue

            # Verify if there are task, acq, or rec pattern matches
            task = ""
            if heuristic == "func":
                task = "task-NoTaskSpecified"
                if tag.get("task_regexp", None):
                    pattern = tag["task_regexp"]
                    re_match = re.search(pattern, dcm_dat, re.IGNORECASE)
                    if re_match:
                        task = re_match.group(0).strip()
                elif tag.get("task_name", None):
                    task = tag["task_name"]

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

            resp_physio = scan.get_resp()
            cardiac_physio = scan.get_cardio()

            curr_map = OrderedDict({
                'subject': "",
                'session': "",
                'bids_type': heuristic,
                'task': task,
                'acq': acq,
                'rec': rec,
                'run': "",
                'modality': tag["bids_modality"],
                'patient_id': curr_dcm.PatientID,
                'scan_datetime': "{}_{}".format(curr_dcm.StudyDate, curr_dcm.StudyTime),
                'scan_dir': os.path.dirname(dcm_file),
                'resp_physio': resp_physio,
                'cardiac_physio': cardiac_physio
            })

            if log:
                log.info("Parsed: {}".format(dcm_file))
                log.debug("Parsed: {} -- Tag: {} --  Dicom Field: {}".format(dcm_file, tag, dcm_dat))
            return curr_map

    log.warning("No tag matches for the specified heuristics found in {}.".format(dcm_file))

    return None


def get_unique_dicoms_from_compressed(compressed_file, dicom_dir, log=None):

    mr_folders_checked = []
    dicom_files = []
    realtime_files = []
    dicom_scans = []

    log.info("Searching for DICOM files in {}...".format(compressed_file))

    try:
        results = check_output('tar -tf {}'.format(compressed_file.strip()),
                               shell=True, universal_newlines=True, stderr=STDOUT)
    except CalledProcessError:
        log.error("Could not open file {}.".format(compressed_file))
        return None

    for result in str(results).strip().split("\n"):

        result = result.strip()
        curr_dir = os.path.dirname(result)

        if result.endswith(".1D"):

            realtime_files.append(result)

        elif curr_dir not in mr_folders_checked and result.endswith(".dcm"):

            dicom_files.append(result)
            mr_folders_checked.append(curr_dir)

    # Create DicomScan objects for each dicom scan and assign relevant physio files if
    # present
    for dicom_file in dicom_files:

        dicom_scan = DicomScan(scan_path=dicom_file, dicom_dir=dicom_dir, compressed=True)

        scan_folder = dicom_scan.get_scan_dir().split("/")[-1].split("_")[-1]
        scan_name = "scan_{}".format(scan_folder)

        for rt_file in realtime_files:

            if ("ECG" in rt_file) and (scan_name in rt_file):

                dicom_scan.set_cardio(rt_file)

            elif ("Resp" in rt_file) and (scan_name in rt_file):

                dicom_scan.set_resp(rt_file)

        dicom_scans.append(dicom_scan)

    return dicom_scans
