from __future__ import print_function, unicode_literals

import os
import io
import dicom

from subprocess import check_output, CalledProcessError, STDOUT
from collections import OrderedDict


def get_sample_dicoms(tgz_file, log=None):

    try:
        dicom_files = check_output('tar -tf {}'.format(tgz_file.strip()),
                                   universal_newlines=True, shell=True, stderr=STDOUT)
    except CalledProcessError:
        if log:
            log.warning("Unable to extract Dicom files from {}".format(tgz_file))
        return tgz_file, []

    seen_dirs = []
    scans_list = []

    for res in str(dicom_files).strip().split("\n"):
        if res.endswith(".dcm"):
            curr_dir = os.path.dirname(res)
            if curr_dir not in seen_dirs:
                scans_list.append(res)
                seen_dirs.append(curr_dir)

    return tgz_file, scans_list


def extract_compressed_dicom_metadata(tgz_file, dcm_file, dicom_tags, log=None):

    metadata = OrderedDict()
    metadata["dicom_file"] = dcm_file

    try:
        dcm_bytes = check_output('tar -O -xf {} {}'.format(tgz_file, dcm_file),
                                 shell=True, stderr=STDOUT)
    except CalledProcessError:
        if log:
            log.warning("Unable to extract {} from {}".format(dcm_file, tgz_file))
        raise Exception("Unable to extract {} from {}".format(dcm_file, tgz_file))

    dcm_fobj = io.BytesIO(dcm_bytes)

    curr_dcm = dicom.read_file(dcm_fobj, stop_before_pixels=True)

    for tag in dicom_tags.keys():
        curr_val = dicom_tags[tag]
        if type(curr_val) == str:
            dcm_group, dcm_element = curr_val.split(",")
            dcm_group = int(dcm_group.strip(), 16)
            dcm_element = int(dcm_element.strip(), 16)
            dcm_dat = curr_dcm.get((dcm_group, dcm_element), None)
            metadata[tag] = dcm_dat.value if dcm_dat else ""
        elif type(curr_val) == list:
            metadata[tag] = ""
            for val in curr_val:
                dcm_group, dcm_element = val.split(",")
                dcm_group = int(dcm_group.strip(), 16)
                dcm_element = int(dcm_element.strip(), 16)
                dcm_dat = curr_dcm.get((dcm_group, dcm_element), None)
                if dcm_dat:
                    metadata[tag] = dcm_dat.value
                    break
        else:
            log.error("Unknown Dicom tag format: {}".format(curr_val))
            raise Exception("Unknown Dicom tag format: {}".format(curr_val))

    return metadata


def extract_uncompressed_dicom_metadata(dcm_file, dicom_tags, log=None):

    metadata = OrderedDict()
    metadata["dicom_file"] = "/".join(dcm_file.split("/")[-4:])

    curr_dcm = dicom.read_file(dcm_file, stop_before_pixels=True)

    for tag in dicom_tags.keys():
        curr_val = dicom_tags[tag]
        if type(curr_val) == str:
            dcm_group, dcm_element = curr_val.split(",")
            dcm_group = int(dcm_group.strip(), 16)
            dcm_element = int(dcm_element.strip(), 16)
            dcm_dat = curr_dcm.get((dcm_group, dcm_element), None)
            metadata[tag] = dcm_dat.value if dcm_dat else ""
        elif type(curr_val) == list:
            metadata[tag] = ""
            for val in curr_val:
                dcm_group, dcm_element = val.split(",")
                dcm_group = int(dcm_group.strip(), 16)
                dcm_element = int(dcm_element.strip(), 16)
                dcm_dat = curr_dcm.get((dcm_group, dcm_element), None)
                if dcm_dat:
                    metadata[tag] = dcm_dat.value
                    break
        else:
            log.error("Unknown Dicom tag format: {}".format(curr_val))
            raise Exception("Unknown Dicom tag format: {}".format(curr_val))

    return metadata
