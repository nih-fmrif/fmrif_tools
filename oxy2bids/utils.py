from __future__ import print_function, unicode_literals

import os
import re
import io
import dicom

from collections import OrderedDict
from subprocess import CalledProcessError, check_output, STDOUT


def parse_dicom(tgz_file, dcm_file, bids_keys, realtime_files=None, log=None):

    try:

        oxy_bytes = check_output('tar -O -xf {} {}'.format(tgz_file, dcm_file),
                                 shell=True, stderr=STDOUT)

    except CalledProcessError:

        log.error("Unable to extract {} from {}".format(dcm_file, tgz_file))
        raise Exception("An error has occurred. Check log for details.")

    oxy_fobj = io.BytesIO(oxy_bytes)

    curr_dcm = dicom.read_file(oxy_fobj, stop_before_pixels=True)

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
            if bids_type == "func":
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

            if log:
                log.info("Parsed: {} -- Tag: {} --  Dicom Field: {}".format(dcm_file, tag, dcm_dat))

            return curr_map

    return None
