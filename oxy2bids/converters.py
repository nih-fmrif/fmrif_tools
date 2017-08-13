from __future__ import print_function, unicode_literals

import os
import shutil
import pandas as pd
import json
import numpy as np

from common_utils.utils import create_path, init_log, get_datetime, get_cpu_count
from subprocess import CalledProcessError, check_output, STDOUT
from glob import glob
from concurrent.futures import ThreadPoolExecutor, wait
from collections import OrderedDict
from shutil import rmtree


LOG_MESSAGES = {
    'success_converted':
        'Converted {} to {}\n'
        'Command:\n{}\n'
        'Return Code:\n{}\n\n',
    'output':
        'Output:\n{}\n\n',
    'dcm2niix_error':
        'Error running dcm2niix on DICOM series in {} directory.\n'
        'Command:\n{}\n'
        'Return Code:\n{}\n\n',
    'tar_error':
        'Error extracting tarred file {}.\n'
        'Command:\n{}\n'
        'Return Code:\n{}\n\n',
    'abort_msg':
        "An error was encountered. See log for details."
}


class BIDSConverter(object):

    def __init__(self, conversion_tool='dcm2niix', log=None):
        self.conversion_tool = conversion_tool
        if log:
            self.log = log
            self.use_outside_log = True
        else:
            self.log = init_log(debug=True)
            self.use_outside_log = False

    def __del__(self):
        if not self.use_outside_log:
            for handler in self.log.handlers:
                self.log.removeHandler(handler)

    @staticmethod
    def physio_to_bids(resp_physio=None, cardiac_physio=None):

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

    @staticmethod
    def parse_bids_map_row(row):

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

        return subject, session, task, acq, rec, run, modality, scan_dir, resp_physio, cardiac_physio

    def _dcm2niix(self, bids_fpath, scan_dir, dicom_dir, physio, compressed, overwrite=False):

        if os.path.isfile(bids_fpath) and not overwrite:
            self.log.error("The file {} already exists, and --overwrite is set to False. Aborting...".format(bids_fpath))
            raise Exception(LOG_MESSAGES['abort_msg'])

        bids_dir = str(os.path.abspath(os.path.dirname(bids_fpath)))
        bids_fname = str(os.path.basename(bids_fpath).split(".")[0])

        # Create the bids output directory if it does not exist
        if not os.path.isdir(bids_dir):
            create_path(bids_dir)

        workdir = bids_dir
        print(workdir)

        if compressed:

            scan_subject, scan_session, scan_folder = scan_dir.strip().split("/")
            compressed_fpath = os.path.join(dicom_dir, "{}-{}-DICOM.tgz".format(scan_subject, scan_session))
            tar_cmd = 'tar -xf {} {}'.format(compressed_fpath, scan_dir)

            try:

                check_output(tar_cmd, shell=True, stderr=STDOUT, cwd=workdir)

                scan_dir = os.path.join(workdir, scan_dir)

            except CalledProcessError as e:

                log_str = LOG_MESSAGES['tar_error'].format(compressed_fpath, tar_cmd, e.returncode)

                if e.output:
                    log_str += LOG_MESSAGES['output'].format(e.output)

                self.log.error(log_str)

                raise Exception(LOG_MESSAGES['abort_msg'])

        else:

            scan_dir = os.path.join(dicom_dir, scan_dir)

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

        try:

            result = check_output(cmd, stderr=STDOUT, cwd=workdir, universal_newlines=True)

            # The following line is a hack to get the actual filename returned by the dcm2niix utility. When converting
            # the B0 dcm files, or files that specify which coil they used, or whether they contain phase information,
            # the utility appends some prefixes to the filename it saves, instead of just using
            # the specified output filename. There is no option to turn this off (and the author seemed unwilling to
            # add one). With this hack I retrieve the actual filename it used to save the file from the utility output.
            # This might break on future updates of dcm2niix
            actual_fname = \
                [s for s in ([s for s in str(result).split('\n') if "Convert" in s][0].split(" "))
                 if s[0] == '/'][0].split("/")[-1]

            print(actual_fname)

            # Move nifti file and json bids file to bids folder
            shutil.move(os.path.join(workdir, "{}.nii.gz".format(actual_fname)),
                        os.path.join(bids_dir, "{}.nii.gz".format(bids_fname)))
            shutil.move(os.path.join(workdir, "{}.json".format(actual_fname)),
                        os.path.join(bids_dir, "{}.json".format(bids_fname)))

            log_str = LOG_MESSAGES['success_converted'].format(scan_dir, bids_fpath, " ".join(cmd), 0)

            if result:
                log_str += LOG_MESSAGES['output'].format(result)

            self.log.info(log_str)

            if physio['resp'] or physio['cardiac']:

                self.log.info("Converting physio files to BIDS...")

                physio_df, physio_meta = self.physio_to_bids(resp_physio=physio['resp'],
                                                             cardiac_physio=physio['cardiac'])

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
            tmp_files = glob(os.path.join(workdir, "*/"))

            if tmp_files:
                list(map(rmtree, tmp_files))

    def convert_to_bids(self, bids_fpath, scan_dir, dicom_dir, physio, compressed, overwrite=False):

        if self.conversion_tool == 'dcm2niix':
            return self._dcm2niix(bids_fpath, scan_dir, dicom_dir, physio, compressed, overwrite)
        else:
            raise Exception(
                "Tool Error: {} is not a supported conversion tool. We only support dcm2niix "
                "at the moment.".format(self.conversion_tool)
            )


def process_bids_map(bids_map, bids_dir, dicom_dir, conversion_tool='dcm2niix', start_datetime=None,
                     log=None, nthreads=get_cpu_count(), overwrite=False):

    start_datetime = start_datetime if start_datetime else get_datetime()

    tmp_dir = os.path.join(os.getcwd(), "tmp-{}".format(start_datetime))

    # Parse bids_map csv table, and create execution list for BIDS generation
    mapping = pd.read_csv(bids_map, header=0, index_col=None)
    mapping.replace(np.nan, '', regex=True, inplace=True)

    # Scans to be converted to bids.
    exec_list = []

    for idx, row in mapping.iterrows():

        subject, session, task, acq, rec, run, modality, scan_dir, \
        resp_physio, cardiac_physio = parse_bids_map_row(row)

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

        exec_list.append({
            'bids_fpath': os.path.join("{}/{}/{}/{}/{}.nii.gz".format(bids_dir, subject, session, row['bids_type'],
                                                                      bids_name)),
            'dicom_dir': dicom_dir,
            'scan_dir': scan_dir,
            'compressed': compressed,
            'physio': {
                'resp': '' if not resp_physio else resp_physio,
                'cardiac': '' if not cardiac_physio else cardiac_physio}
        })

    # Convert files to Nifti
    with ThreadPoolExecutor(max_workers=nthreads) as executor:

        converter = BIDSConverter(conversion_tool=conversion_tool, log=log)
        futures = []

        for exec_item in exec_list:
            futures.append(executor.submit(converter.convert_to_bids,
                                           exec_item['bids_fpath'],
                                           exec_item['scan_dir'],
                                           exec_item['dicom_dir'],
                                           exec_item['physio'],
                                           exec_item['compressed'],
                                           overwrite))
        wait(futures)

        success = True

        for future in futures:

            if not future.result():
                success = False
                break

        if not success:
            log.error("There were errors converting the provided datasets to BIDS format. See log for more"
                      " information.")

    # Remove tmp dir if it was created
    if os.path.isdir(tmp_dir):
        log.info("Removing temporary files")
        shutil.rmtree(tmp_dir)
