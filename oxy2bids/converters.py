from __future__ import print_function, unicode_literals

import os
import shutil
import pandas as pd
import numpy as np
import random
import string
import json

from subprocess import CalledProcessError, check_output, STDOUT
from glob import glob
from concurrent.futures import ThreadPoolExecutor, wait
from oxy2bids.utils import create_path, extract_tgz, init_log
from datetime import datetime
from collections import OrderedDict


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
    'dimon_error':
        'Error running Dimon on DICOM series in {} directory.\n'
        'Command:\n{}\n'
        'Return Code:\n{}\n\n',
}

DATE_STR = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


class NiftyConversionFailure(Exception):
    def __init__(self, message):
        self.message = message


class DuplicateFile(Exception):
    def __init__(self, message):
        self.message = message


class BIDSConverter(object):

    use_outside_log = False

    def __init__(self, conversion_tool='dcm2niix', log=None):
        self.conversion_tool = conversion_tool
        if log:
            self.log = log
            self.use_outside_log = True
        else:
            self.log = init_log(debug=True)

    def __del__(self):
        if not self.use_outside_log:
            for handler in self.log.handlers:
                self.log.removeHandler(handler)

    def physio_to_bids(self, bids_fname, bids_dir, resp_physio=None, cardiac_physio=None):

        if resp_physio or cardiac_physio:

            self.log.info("Converting physio files to BIDS...")
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

            # Save TSV file
            if bids_fname.endswith('_bold'):
                bids_fname = bids_fname[:-5]

            physio_df.to_csv(os.path.join(bids_dir, "{}_physio.tsv.gz".format(bids_fname)), sep="\t", index=False,
                             header=False, compression="gzip")

            physio_meta = OrderedDict({
                "SamplingFrequency": 50,
                "StartTime": 0,
                "Columns": cols
            })

            with open(os.path.join(bids_dir, "{}_physio.json".format(bids_fname)), 'w') as physio_json:
                json.dump(physio_meta, physio_json)

            self.log.info("Finished converting physio files to BIDS...")

    def convert_to_bids(self, bids_fpath, dcm_dir, physio):

        if self.conversion_tool == 'dcm2niix':
            return self._dcm2niix(bids_fpath, dcm_dir)
        # elif self.conversion_tool == 'dimon':
        #     self._dimon(bids_fpath, dcm_dir)
        else:
            raise NiftyConversionFailure(
                "Tool Error: {} is not a supported conversion tool. Please select 'dcm2niix' or "
                "'dimon'".format(self.conversion_tool))

    def _dcm2niix(self, bids_fpath, dcm_dir, physio):

        bids_dir = os.path.abspath(os.path.dirname(bids_fpath))
        print(bids_dir)
        bids_fname = os.path.basename(bids_fpath).split(".")[0]

        # Create the bids output directory if it does not exist
        if not os.path.isdir(bids_dir):
            create_path(bids_dir)

        workdir = dcm_dir

        cmd = [
                "dcm2niix",
                "-z",
                "y",
                "-b",
                "y",
                "-f",
                bids_fname,
                dcm_dir
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

            # Move nifti file and json bids file to bids folder
            shutil.move(os.path.join(workdir, "{}.nii.gz".format(actual_fname)),
                        os.path.join(bids_dir, "{}.nii.gz".format(bids_fname)))
            shutil.move(os.path.join(workdir, "{}.json".format(actual_fname)),
                        os.path.join(bids_dir, "{}.json".format(bids_fname)))

            log_str = LOG_MESSAGES['success_converted'].format(dcm_dir, bids_fpath, " ".join(cmd), 0)

            if result:
                log_str += LOG_MESSAGES['output'].format(result)

            self.log.info(log_str)

            if physio['resp'] or physio['cardiac']:

                self.physio_to_bids(bids_fname=bids_fname, bids_dir=bids_dir, resp_physio=physio['resp'],
                                    cardiac_physio=physio['cardiac'])

            return dcm_dir, True

        except CalledProcessError as e:

            log_str = LOG_MESSAGES['dcm2niix_error'].format(dcm_dir, " ".join(cmd), e.returncode)

            if e.output:
                log_str += LOG_MESSAGES['output'].format(e.output)

            self.log.error(log_str)

            return dcm_dir, False

        finally:

            # Clean up temporary files
            tmp_files = glob(os.path.join(workdir, "*.nii.gz"))
            tmp_files.extend(glob(os.path.join(workdir, "*.json")))

            if tmp_files:
                list(map(os.remove, tmp_files))

    # def _dimon(self, bids_fpath, dcm_fpath):
    #     pass
    #
    #     dcm_dir = os.path.dirname(dcm_fpath)
    #
    #     bids_dir = os.path.dirname(bids_fpath)
    #     bids_fname = os.path.basename(bids_fpath).split(".")[0]
    #
    #     # Create the bids output directory if it does not exist
    #     if not os.path.isdir(os.path.dirname(bids_dir)):
    #         create_path(os.path.dirname(bids_dir))
    #
    #     workdir = dcm_dir
    #
    #     # IMPLEMENT GENERATION OF BIDS METADATA FILES WHEN USING DIMON FOR CONVERSION OF DCM FILES
    #
    #     cmd = [
    #         "Dimon",
    #         "-infile_pattern",
    #         os.path.join(workdir, "*.dcm"),
    #         "-gert_create_dataset",
    #         "-gert_quit_on_err",
    #         "-gert_to3d_prefix",
    #         "{}.nii.gz".format(bids_fname)
    #     ]
    #
    #     dimon_env = os.environ.copy()
    #     dimon_env['AFNI_TO3D_OUTLIERS'] = 'No'
    #
    #     try:
    #
    #         result = check_output(cmd, stderr=STDOUT, env=dimon_env, cwd=workdir, universal_newlines=True)
    #
    #         # Check the contents of stdout for the -quit_on_err flag because to3d returns a success code
    #         # even if it terminates because the -quit_on_err flag was thrown
    #         if "to3d kept from going into interactive mode by option -quit_on_err" in result:
    #
    #             log_str = LOG_MESSAGES['dimon_error'].format(dcm_fpath, " ".join(cmd), 0)
    #
    #             if result:
    #                 log_str += LOG_MESSAGES['output'].format(result)
    #
    #             self.log.info(log_str)
    #
    #             return dcm_fpath, False
    #
    #         shutil.move(os.path.join(workdir, "{}.nii.gz".format(out_fpath)),
    #                     os.path.join(os.path.dirname(bids_fpath), "{}.nii.gz".format(out_fname)))
    #
    #         dcm_file = [f for f in os.listdir(dcm_dir) if ".dcm" in f][0]
    #
    #         log_str = LOG_MESSAGES['success_converted'].format(os.path.join(dcm_dir, dcm_file), out_fname,
    #                                                            " ".join(cmd), 0)
    #
    #         if result:
    #             log_str += LOG_MESSAGES['output'].format(result)
    #
    #         log_output(log_str, logger=logger, semaphore=semaphore)
    #
    #         return dcm_dir, True
    #
    #     except CalledProcessError as e:
    #
    #         log_str = LOG_MESSAGES['dimon_error'].format(dcm_dir, " ".join(cmd), e.returncode)
    #
    #         if e.output:
    #             log_str += LOG_MESSAGES['output'].format(e.output)
    #
    #         log_output(log_str, level="ERROR", logger=logger, semaphore=semaphore)
    #
    #         return dcm_dir, False
    #
    #     finally:
    #
    #         # Clean up temporary files
    #         tmp_files = glob(os.path.join(dimon_workdir, "GERT_Reco_dicom*"))
    #         tmp_files.extend(glob(os.path.join(dimon_workdir, "dimon.files.run.*")))
    #
    #         if tmp_files:
    #             list(map(os.remove, tmp_files))
    #


def parse_bids_map_row(row):

    subject = row['subject']
    session = row['session']
    task = row['task']
    acq = row['acq']
    rec = row['rec']
    run = row['run']
    modality = row['modality']
    oxy_file = row['oxy_file']
    scan_dir = row['scan_dir']
    resp_physio = row['resp_physio']
    cardiac_physio = row['cardiac_physio']

    return subject, session, task, acq, rec, run, modality, oxy_file, scan_dir, resp_physio, cardiac_physio


def process_bids_map(bids_map, bids_dir, dicom_dir, conversion_tool='dcm2niix', start_datetime=None, log=None,
                     nthreads=0, overwrite=False):

    if not start_datetime:
        start_datetime = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")

    tmp_dir = os.path.join(os.getcwd(), "tmp-{}".format(start_datetime))

    # Parse bids_map csv table, and create execution list for BIDS generation
    mapping = pd.read_csv(bids_map, header=0, index_col=None)
    mapping.replace(np.nan, '', regex=True, inplace=True)

    tgz_files = {}
    exec_list = []

    for idx, row in mapping.iterrows():

        subject, session, task, acq, rec, run, modality, oxy_file, \
        scan_dir, resp_physio, cardio_physio = parse_bids_map_row(row)

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

        oxy_fpath = os.path.join(dicom_dir, oxy_file)
        if tgz_files.get(oxy_fpath, None) is None:
            tgz_files[oxy_fpath] = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(10))

        exec_list.append({
            'bids_fpath': os.path.join("{}/{}/{}/{}/{}.nii.gz".format(bids_dir, subject, session, row['bids_type'],
                                                                      bids_name)),
            'scan_dir': os.path.join(tmp_dir, tgz_files[oxy_fpath], scan_dir),
            'physio': {'resp': resp_physio, 'cardiac': cardio_physio}
        })

    if nthreads < 2:  # Process sequentially

        # Extract the TGZ files
        for tgz_file in tgz_files.keys():
            extract_tgz(tgz_file, out_path=os.path.join(tmp_dir, tgz_files[tgz_file]), log=log)

        # Convert files to NIFTI
        converter = BIDSConverter(conversion_tool=conversion_tool, log=log)
        for exec_item in exec_list:
            converter.convert_to_bids(exec_item['bids_fpath'], exec_item['scan_dir'], exec_item['physio'])

    else:

        # Extract TGZ files
        with ThreadPoolExecutor(max_workers=nthreads) as executor:

            futures = []

            for tgz_file in tgz_files.keys():
                futures.append(executor.submit(extract_tgz, tgz_file,
                                               out_path=os.path.join(tmp_dir, tgz_files[tgz_file]), log=log))
            wait(futures)

            for future in futures:
                tgz_fpath, success = future.result()

                if not success:
                    log.error("Could not extract file {}".format(tgz_fpath))

        # Convert files to Nifti
        with ThreadPoolExecutor(max_workers=nthreads) as executor:

            converter = BIDSConverter(conversion_tool=conversion_tool, log=log)
            futures = []

            for exec_item in exec_list:
                futures.append(executor.submit(converter.convert_to_bids, exec_item['bids_fpath'],
                                               exec_item['scan_dir'], exec_item['physio']))
            wait(futures)

            for future in futures:

                dcm_dir, success = future.result()

                if not success:
                    log.error("Could not convert DICOM series in {}".format(dcm_dir))

    # Remove tmp dir if it was created
    if os.path.isdir(tmp_dir):
        log.info("Removing temporary files")
        shutil.rmtree(tmp_dir)
