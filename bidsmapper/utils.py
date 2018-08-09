from __future__ import print_function, unicode_literals

import os
import re
import io
import pydicom

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


def get_dicom_dat(field, dcm_file, dicom_tags):

    dcm_fields = [dicom_tags[field]] if not isinstance(dicom_tags[field], list) else dicom_tags[field]

    for dcm_field in dcm_fields:

        dcm_group, dcm_element = dcm_field.split(",")
        dcm_group = int(dcm_group.strip(), 16)
        dcm_element = int(dcm_element.strip(), 16)

        dcm_dat = dcm_file.get((dcm_group, dcm_element), None)

        if dcm_dat:
            return dcm_dat

    return None


def dicom_parser(scan, bids_tags, dicom_tags, log=None):

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

        print(oxy_fobj)

        curr_dcm = pydicom.dcmread(oxy_fobj, stop_before_pixels=True)

    else:

        curr_dcm = pydicom.dcmread(dcm_file, stop_before_pixels=True)

    print(curr_dcm)

    for modality in bids_tags.keys():

        # Iterate through the tags for the current bids modality, see if they
        # match the current data in the specified dicom field

        for bids_tag in bids_tags[modality]:

            include_tags = bids_tag.get("include", None)
            exclude_tags = bids_tag.get("exclude", None)

            # Verify that all the keywords in the 'include' fields are present

            pass_include = True

            for tag in include_tags:

                if not pass_include:
                    break

                dicom_field, expr = tag

                dicom_dat = get_dicom_dat(dicom_field, curr_dcm, dicom_tags)

                if not dicom_dat:
                    pass_include = False
                    break

                if expr.startswith("re::"):
                    pattern = r"{}".format(expr[4:])
                    re_match = re.search(pattern, dicom_dat, re.IGNORECASE)
                    if re_match:
                        continue
                elif expr.lower() in str(dicom_dat.value).lower():
                    continue

                pass_include = False

            if not pass_include:
                continue

            # Verify that none of the keywords in the 'exclude' field are present

            pass_exclude = True

            for tag in exclude_tags:

                if not pass_exclude:
                    break

                dicom_field, expr = tag

                dicom_dat = get_dicom_dat(dicom_field, curr_dcm, dicom_tags)

                if expr.startswith("re::"):
                    pattern = r"{}".format(expr[4:])
                    re_match = re.search(pattern, dicom_dat, re.IGNORECASE)
                    if re_match:
                        pass_exclude = False
                        break
                elif expr.lower() in str(dicom_dat.value).lower():
                    pass_exclude = False
                    break

            if not pass_exclude:
                continue

            # Verify if there are task, acq, or rec pattern matches
            task = ""
            if modality == "func":
                task_tags = bids_tag.get("task", None)
                if task_tags:
                    task_field, task_expr = task_tags
                    task_dat = get_dicom_dat(task_field, curr_dcm, dicom_tags)
                    if task_dat:
                        task_dat = str(task_dat.value)
                        if task_expr.startswith("re::"):
                            pattern = r"{}".format(task_expr[4:])
                            re_match = re.search(pattern, task_dat, re.IGNORECASE)
                            if re_match:
                                task = re_match.group(0).strip()
                            else:
                                task = "task-NotSpecified"
                        else:
                            task = task_expr
                    else:
                        task = "task-NotSpecified"
                else:
                    task = "task-NotSpecified"

            acq = ""
            acq_tags = bids_tag.get("acq", None)
            if acq_tags:
                acq_field, acq_expr = acq_tags
                acq_dat = get_dicom_dat(acq_field, curr_dcm, dicom_tags)
                if acq_dat:
                    acq_dat = str(acq_dat.value)
                    if acq_expr.startswith("re::"):
                        pattern = r"{}".format(acq_expr[4:])
                        re_match = re.search(pattern, acq_dat, re.IGNORECASE)
                        if re_match:
                            acq = re_match.group(0).strip()
                    else:
                        acq = acq_expr

            rec = ""
            rec_tags = bids_tag.get("rec", None)
            if rec_tags:
                rec_field, rec_expr = rec_tags
                rec_dat = get_dicom_dat(rec_field, curr_dcm, dicom_tags)
                if rec_dat:
                    rec_dat = str(rec_dat.value)
                    if rec_expr.startswith("re::"):
                        pattern = r"{}".format(rec_expr[4:])
                        re_match = re.search(pattern, rec_dat, re.IGNORECASE)
                        if re_match:
                            rec = re_match.group(0).strip()
                    else:
                        rec = rec_expr

            resp_physio = scan.get_resp()
            cardiac_physio = scan.get_cardio()

            curr_map = OrderedDict({
                'subject': "",
                'session': "",
                'bids_type': modality,
                'task': task,
                'acq': acq,
                'rec': rec,
                'run': "",
                'modality': bids_tag["bids_modality"],
                'patient_id': curr_dcm.PatientID,
                'scan_datetime': "{}_{}".format(curr_dcm.StudyDate, curr_dcm.StudyTime),
                'scan_dir': os.path.dirname(dcm_file),
                'resp_physio': resp_physio,
                'cardiac_physio': cardiac_physio,
                'biopac': ""  # NOT IMPLEMENTED
            })

            if log:
                log.info("Parsed: {}".format(dcm_file))
                log.debug("Parsed: {} -- Tag: {}".format(dcm_file, bids_tag))
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

        scan_folder = str(dicom_scan.get_scan_dir()).split("/")[-1].split("_")[-1]
        scan_name = "scan_{}".format(scan_folder)

        for rt_file in realtime_files:

            if ("ECG" in rt_file) and (scan_name in rt_file):

                dicom_scan.set_cardio(rt_file)

            elif ("Resp" in rt_file) and (scan_name in rt_file):

                dicom_scan.set_resp(rt_file)

        dicom_scans.append(dicom_scan)

    return dicom_scans
