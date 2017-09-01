from __future__ import print_function, unicode_literals

import os
import re
import shutil
import pandas as pd
import json
import numpy as np
import string
import random
import struct

from glob import glob
from shutil import rmtree
from collections import OrderedDict
from oxy2bids.constants import LOG_MESSAGES
from biounpacker.biopac_organize import biounpacker
from common_utils.utils import create_path, init_log, get_cpu_count
from subprocess import CalledProcessError, check_output, STDOUT
from concurrent.futures import ThreadPoolExecutor, wait


class BIDSConverter(object):

    def __init__(self, conversion_tool='dcm2niix', log=None):
        self.conversion_tool = conversion_tool
        if log:
            self.log = log
            self.use_outside_log = True
        else:
            self.log = init_log(log_name='BIDSConverter', debug=True)
            self.use_outside_log = False

    def __del__(self):
        if not self.use_outside_log:
            for handler in self.log.handlers:
                self.log.removeHandler(handler)

    def _physio_to_bids(self, resp_physio=None, cardiac_physio=None):

        physio_df = pd.DataFrame()
        cols = []

        if cardiac_physio:
            cardio_df = pd.read_csv(cardiac_physio, sep="\n", header=None, names=["cardiac"])
            physio_df = physio_df.append(cardio_df)
            cols.append("cardiac")

        if resp_physio:
            resp_df = pd.read_csv(resp_physio, sep="\n", header=None, names=["respiratory"])
            physio_df = physio_df.join(resp_df)
            cols.append("respiratory")

        physio_meta = OrderedDict({
            "SamplingFrequency": 50,
            "StartTime": 0,
            "Columns": cols
        })

        return physio_df, physio_meta

    def _biopac_to_bids(self, biopac_file):

        physio_df = pd.DataFrame()
        cols = []

        biopac_channels = biounpacker(biopac_file)

        if biopac_channels['ecg']:
            cardio_df = pd.DataFrame(biopac_channels['ecg'].data, columns=["cardiac"])
            physio_df = physio_df.append(cardio_df)
            cols.append("cardiac")

        if biopac_channels['resp']:
            resp_df = pd.DataFrame(biopac_channels['resp'].data, columns=["respiratory"])
            physio_df = physio_df.join(resp_df)
            cols.append("respiratory")

        if biopac_channels['triggers']:
            trigger_df = pd.DataFrame(biopac_channels['triggers'].data, columns=["triggers"])
            physio_df = physio_df.join(trigger_df)
            cols.append("triggers")

        physio_meta = OrderedDict({
            "SamplingFrequency": biopac_channels['resp'].samples_per_second,
            "StartTime": biopac_channels['resp'].time_index[0],
            "Columns": cols
        })

        return physio_df, physio_meta

    def _dcm2niix(self, bids_fpath, scan_dir, dicom_dir, physio, compressed, biopac_dir=None, overwrite=False):

        if os.path.isfile(bids_fpath) and not overwrite:
            self.log.error("The file {} already exists, and --overwrite is set to "
                           "False. Aborting...".format(bids_fpath))
            raise Exception(LOG_MESSAGES['abort_msg'])

        bids_dir = str(os.path.abspath(os.path.dirname(bids_fpath)))
        bids_fname = str(os.path.basename(bids_fpath).split(".")[0])

        # Create the bids output directory if it does not exist
        if not os.path.isdir(bids_dir):
            create_path(bids_dir)

        tmp_dir = "tmp_{}".format(''.join(random.choice(
            string.ascii_uppercase + string.digits) for _ in range(10)))

        if compressed:

            workdir = os.path.join(bids_dir, tmp_dir)
            create_path(workdir)

            scan_subject, scan_session, scan_folder = scan_dir.strip().split("/")
            compressed_fpath = os.path.join(dicom_dir, "{}-{}-DICOM.tgz".format(scan_subject, scan_session))
            tar_cmd = 'tar -xf {} {}'.format(compressed_fpath, scan_dir)

            # Extract dicom file
            try:

                check_output(tar_cmd, shell=True, stderr=STDOUT, cwd=workdir)
                scan_dir = os.path.join(workdir, scan_dir)

            except CalledProcessError as e:

                log_str = LOG_MESSAGES['tar_error'].format(compressed_fpath, tar_cmd, e.returncode)

                if e.output:
                    log_str += LOG_MESSAGES['output'].format(e.output)

                self.log.error(log_str)
                raise Exception(LOG_MESSAGES['abort_msg'])

            # Extract physio files if present (SIEMENS)
            if physio['cardiac']:

                try:

                    tar_cmd = 'tar -xf {} {}'.format(compressed_fpath, physio['cardiac'])
                    check_output(tar_cmd, shell=True, stderr=STDOUT, cwd=workdir)

                except CalledProcessError as e:

                    log_str = LOG_MESSAGES['tar_error'].format(compressed_fpath, tar_cmd, e.returncode)

                    if e.output:
                        log_str += LOG_MESSAGES['output'].format(e.output)

                    self.log.error(log_str)
                    raise Exception(LOG_MESSAGES['abort_msg'])

            if physio['resp']:

                try:

                    tar_cmd = 'tar -xf {} {}'.format(compressed_fpath, physio['resp'])
                    check_output(tar_cmd, shell=True, stderr=STDOUT, cwd=workdir)

                except CalledProcessError as e:

                    log_str = LOG_MESSAGES['tar_error'].format(compressed_fpath, tar_cmd, e.returncode)

                    if e.output:
                        log_str += LOG_MESSAGES['output'].format(e.output)

                    self.log.error(log_str)

                    raise Exception(LOG_MESSAGES['abort_msg'])

        else:

            workdir = bids_dir

            scan_dir = os.path.join(dicom_dir, scan_dir)

        try:

            cmd = [
                "dcm2niix",
                "-z",
                "y",
                "-b",
                "y",
                "-f",
                bids_fname,
                scan_dir
            ]

            result = check_output(cmd, stderr=STDOUT, cwd=workdir, universal_newlines=True)

            # The following line is a hack to get the actual filename returned by the dcm2niix utility. When converting
            # the B0 dcm files, or files that specify which coil they used, or whether they contain phase information,
            # the utility appends some prefixes to the filename it saves, instead of just using
            # the specified output filename. There is no option to turn this off (and the author seemed unwilling to
            # add one). With this hack I retrieve the actual filename it used to save the file from the utility output.
            # This might break on future updates of dcm2niix
            pattern = r'(/.*?\.?[^\(]*)'
            match = re.search(pattern, result)
            actual_fname = os.path.basename(match.group().strip())

            # Move nifti file and json bids file to bids folder
            shutil.move(os.path.join(scan_dir, "{}.nii.gz".format(actual_fname)),
                        os.path.join(bids_dir, "{}.nii.gz".format(bids_fname)))
            shutil.move(os.path.join(scan_dir, "{}.json".format(actual_fname)),
                        os.path.join(bids_dir, "{}.json".format(bids_fname)))

            # If the scan is a DTI scan, move over the bval and bvec files too
            if "_dwi" in bids_fname:

                # Need to verify the .bval and .bvec files got created, because sometimes they fail
                # without throwing an error in dcm2niix
                if os.path.isfile(os.path.join(scan_dir, "{}.bval".format(actual_fname))):

                    shutil.move(os.path.join(scan_dir, "{}.bval".format(actual_fname)),
                                os.path.join(bids_dir, "{}.bval".format(bids_fname)))

                if os.path.isfile(os.path.join(scan_dir, "{}.bvec".format(actual_fname))):

                    shutil.move(os.path.join(scan_dir, "{}.bvec".format(actual_fname)),
                                os.path.join(bids_dir, "{}.bvec".format(bids_fname)))

            log_str = LOG_MESSAGES['success_converted'].format(scan_dir, bids_fpath, " ".join(cmd), 0)

            if result:
                log_str += LOG_MESSAGES['output'].format(result)

            self.log.info(log_str)

            if physio['biopac']:

                if not biopac_dir:
                    err_msg = "Attempted to process biopac file {} but biopac directory was not " \
                              "specified.".format(physio['biopac'])
                    self.log.error(err_msg)
                    raise Exception(err_msg)

                self.log.info("Converting biopac file to BIDS format...")

                try:

                    physio_df, physio_meta = self._biopac_to_bids(os.path.join(biopac_dir, physio['biopac']))

                    bids_fname = bids_fname[:-5] if bids_fname.endswith('_bold') else bids_fname

                    physio_df.to_csv(os.path.join(bids_dir, "{}_physio.tsv.gz".format(bids_fname)), sep="\t", index=False,
                                     header=False, compression="gzip")

                    with open(os.path.join(bids_dir, "{}_physio.json".format(bids_fname)), 'w') as physio_json:
                        json.dump(physio_meta, physio_json)

                    self.log.info("Finished converting biopac to BIDS format...")

                except struct.error:

                    self.log.error("There was an error opening biopac file {}.".format(physio['biopac']))

            elif physio['resp'] or physio['cardiac']:

                if compressed:
                    resp_physio = os.path.join(workdir, physio['resp'])
                    cardiac_physio = os.path.join(workdir, physio['cardiac'])
                else:
                    resp_physio = os.path.join(dicom_dir, physio['resp'])
                    cardiac_physio = os.path.join(dicom_dir, physio['cardiac'])

                self.log.info("Converting physio files to BIDS...")

                physio_df, physio_meta = self._physio_to_bids(resp_physio=resp_physio,
                                                              cardiac_physio=cardiac_physio)

                bids_fname = bids_fname[:-5] if bids_fname.endswith('_bold') else bids_fname

                physio_df.to_csv(os.path.join(bids_dir, "{}_physio.tsv.gz".format(bids_fname)), sep="\t", index=False,
                                 header=False, compression="gzip")

                with open(os.path.join(bids_dir, "{}_physio.json".format(bids_fname)), 'w') as physio_json:
                    json.dump(physio_meta, physio_json)

                self.log.info("Finished converting physio files to BIDS...")

            return True

        except CalledProcessError as e:

            log_str = LOG_MESSAGES['dcm2niix_error'].format(scan_dir, " ".join(cmd), e.returncode)

            if e.output:
                log_str += LOG_MESSAGES['output'].format(e.output)

            self.log.error(log_str)

            raise Exception(LOG_MESSAGES['abort_msg'])

        finally:
            # Clean up temporary files
            tmp_files = glob(os.path.join(bids_dir, tmp_dir))

            if tmp_files:
                list(map(rmtree, tmp_files))

    def _convert_to_bids(self, bids_fpath, scan_dir, dicom_dir, physio, compressed, biopac_dir=None, overwrite=False):

        if self.conversion_tool == 'dcm2niix':
            return self._dcm2niix(bids_fpath, scan_dir, dicom_dir, physio, compressed, biopac_dir, overwrite)
        else:
            raise Exception(
                "Tool Error: {} is not a supported conversion tool. We only support dcm2niix "
                "at the moment.".format(self.conversion_tool)
            )

    def map_to_bids(self, bids_map, bids_dir, dicom_dir, nthreads=get_cpu_count(), biopac_dir=None, overwrite=False):

        # Parse bids_map csv table, and create execution list for BIDS generation
        mapping = pd.read_csv(bids_map, header=0, index_col=None)
        mapping.replace(np.nan, '', regex=True, inplace=True)

        with ThreadPoolExecutor(max_workers=nthreads) as executor:

            futures = []

            for _, row in mapping.iterrows():
                futures.append(executor.submit(self._process_map_row, row, bids_dir, dicom_dir, self.conversion_tool,
                                               biopac_dir, overwrite))

            wait(futures)

            success = True

            for future in futures:

                if not future.result():
                    success = False
                    break

            if not success:
                self.log.error("There were errors converting the provided datasets to BIDS format. See log for more" 
                               " information.")

    def _process_map_row(self, row, bids_dir, dicom_dir, conversion_tool='dcm2niix', biopac_dir=None, overwrite=False):

        # Construct the BIDS filename based on the metadata provided in the row

        subject = row['subject']
        session = row['session']
        task = row['task']
        acq = row['acq']
        rec = row['rec']
        run = row['run']
        modality = row['modality']
        scan_dir = row['scan_dir']
        resp_physio = row['resp_physio']
        cardiac_physio = row['cardiac_physio']
        biopac = row.get('biopac', None)

        bids_name = subject

        if session:
            bids_name += '_{}'.format(session)

        if row['bids_type'] == 'anat':

            if acq:
                bids_name += '_{}'.format(acq)

            if rec:
                bids_name += '_{}'.format(rec)

            if run:
                bids_name += '_{}'.format(run)

            bids_name += '_{}'.format(modality)

        elif row['bids_type'] == 'func':

            bids_name += '_{}'.format(task)

            if acq:
                bids_name += '_{}'.format(acq)

            if rec:
                bids_name += '_{}'.format(rec)

            if run:
                bids_name += '_{}'.format(run)

            bids_name += '_{}'.format(modality)

        elif row['bids_type'] == 'dwi':

            if acq:
                bids_name += '_{}'.format(acq)

            if run:
                bids_name += '_{}'.format(run)

            bids_name += '_{}'.format(modality)

        elif row['bids_type'] == 'fmap':

            if acq:
                bids_name += '_{}'.format(acq)

            if "dir" in modality:
                bids_name += '_{}'.format(modality)

            if run:
                bids_name += '_{}'.format(run)

            if "dir" in modality:
                bids_name += '_epi'
            else:
                bids_name += '_{}'.format(modality)

        # Get the directory of the scan files relative to the dicom directory, and determine whether
        # the scan is in an uncompressed directory already, or if extraction is needed
        compressed = False if os.path.isdir(os.path.join(dicom_dir, scan_dir)) else True

        # Based on the above information, compute the execution params
        exec_params = OrderedDict({
            'conversion_tool': conversion_tool,
            'bids_fpath': os.path.join("{}/{}/{}/{}/{}.nii.gz".format(bids_dir, subject, session, row['bids_type'],
                                                                      bids_name)),
            'dicom_dir': dicom_dir,
            'scan_dir': scan_dir,
            'compressed': compressed,
            'physio': {
                'resp': '' if not resp_physio else resp_physio,
                'cardiac': '' if not cardiac_physio else cardiac_physio,
                'biopac': '' if not biopac else biopac
            },
            'biopac_dir': biopac_dir,
            'overwrite': overwrite
        })

        # Convert the file to BIDS format
        success = self._convert_to_bids(
            bids_fpath=exec_params['bids_fpath'],
            scan_dir=exec_params['scan_dir'],
            dicom_dir=exec_params['dicom_dir'],
            physio=exec_params['physio'],
            compressed=exec_params['compressed'],
            biopac_dir=exec_params['biopac_dir'],
            overwrite=exec_params['overwrite']
        )

        return success
