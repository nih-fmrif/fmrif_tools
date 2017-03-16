import os
import shutil
import dicom
import json
from subprocess import CalledProcessError, check_output, STDOUT
from glob import glob
from concurrent.futures import ThreadPoolExecutor, wait
from utils import log_output, create_path, extract_tgz, MAX_WORKERS, get_modality
from threading import Semaphore
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


class NiftyConversionFailure(Exception):
    def __init__(self, message):
        self.message = message


class DuplicateFile(Exception):
    def __init__(self, message):
        self.message = message


def dcm_to_nifti(dcm_dir, out_fname, out_dir, conversion_tool='dcm2niix', logger=None, bids_meta=False, semaphore=None):

    # Create the bids output directory if it does not exist
    if not os.path.isdir(out_dir):
        create_path(out_dir, semaphore=semaphore)

    if conversion_tool == 'dcm2niix':

        dcm2niix_workdir = dcm_dir

        if bids_meta:
            cmd = [
                "dcm2niix",
                "-z",
                "y",
                "-b",
                "y",
                "-f",
                out_fname,
                dcm_dir
            ]
        else:
            cmd = [
                "dcm2niix",
                "-z",
                "y",
                "-f",
                out_fname,
                dcm_dir
            ]

        try:

            result = check_output(cmd, stderr=STDOUT, cwd=dcm2niix_workdir, universal_newlines=True)

            # The following line is a hack to get the actual filename returned by the dcm2niix utility. When converting
            # the B0 dcm files, or files that specify which coil they used, or whether they contain phase information,
            # the utility appends some prefixes to the filename it saves, instead of just using
            # the specified output filename. There is no option to turn this off (and the author seemed unwilling to
            # add one). With this hack I retrieve the actual filename it used to save the file from the utility output.
            # This might break on future updates of dcm2niix
            actual_fname = \
                [s for s in ([s for s in str(result).split('\n') if "Convert" in s][0].split(" "))
                 if s[0] == '/'][0].split("/")[-1]

            # Move nifti file and json bids file to anat folder
            shutil.move(os.path.join(dcm_dir, "{}.nii.gz".format(actual_fname)),
                        os.path.join(out_dir, "{}.nii.gz".format(out_fname)))
            shutil.move(os.path.join(dcm_dir, "{}.json".format(actual_fname)),
                        os.path.join(out_dir, "{}.json".format(out_fname)))

            dcm_file = [f for f in os.listdir(dcm_dir) if ".dcm" in f][0]

            log_str = LOG_MESSAGES['success_converted'].format(os.path.join(dcm_dir, dcm_file), out_fname,
                                                               " ".join(cmd), 0)

            if result:
                log_str += LOG_MESSAGES['output'].format(result)

            log_output(log_str, logger=logger, semaphore=semaphore)

            return dcm_dir, True

        except CalledProcessError as e:

            log_str = LOG_MESSAGES['dcm2niix_error'].format(dcm_dir, " ".join(cmd), e.returncode)

            if e.output:
                log_str += LOG_MESSAGES['output'].format(e.output)

            log_output(log_str, level="ERROR", logger=logger, semaphore=semaphore)

            return dcm_dir, False

        finally:

            # Clean up temporary files
            tmp_files = glob(os.path.join(dcm2niix_workdir, "*.nii.gz"))
            tmp_files.extend(glob(os.path.join(dcm2niix_workdir, "*.json")))

            if tmp_files:
                list(map(os.remove, tmp_files))

    elif conversion_tool == 'dimon':

        dimon_workdir = dcm_dir

        # IMPLEMENT GENERATION OF BIDS METADATA FILES WHEN USING DIMON FOR CONVERSION OF DCM FILES

        cmd = [
            "Dimon",
            "-infile_pattern",
            os.path.join(dcm_dir, "*.dcm"),
            "-gert_create_dataset",
            "-gert_quit_on_err",
            "-gert_to3d_prefix",
            "{}.nii.gz".format(out_fname)
        ]

        dimon_env = os.environ.copy()
        dimon_env['AFNI_TO3D_OUTLIERS'] = 'No'

        try:

            result = check_output(cmd, stderr=STDOUT, env=dimon_env, cwd=dimon_workdir, universal_newlines=True)

            # Check the contents of stdout for the -quit_on_err flag because to3d returns a success code
            # even if it terminates because the -quit_on_err flag was thrown
            if "to3d kept from going into interactive mode by option -quit_on_err" in result:

                log_str = LOG_MESSAGES['dimon_error'].format(dcm_dir, " ".join(cmd), 0)

                if result:
                    log_str += LOG_MESSAGES['output'].format(result)

                log_output(log_str, level="ERROR", logger=logger, semaphore=semaphore)

                return dcm_dir, False

            shutil.move(os.path.join(dimon_workdir, "{}.nii.gz".format(out_fname)),
                        os.path.join(out_dir, "{}.nii.gz".format(out_fname)))

            dcm_file = [f for f in os.listdir(dcm_dir) if ".dcm" in f][0]

            log_str = LOG_MESSAGES['success_converted'].format(os.path.join(dcm_dir, dcm_file), out_fname,
                                                               " ".join(cmd), 0)

            if result:
                log_str += LOG_MESSAGES['output'].format(result)

            log_output(log_str, logger=logger, semaphore=semaphore)

            return dcm_dir, True

        except CalledProcessError as e:

            log_str = LOG_MESSAGES['dimon_error'].format(dcm_dir, " ".join(cmd), e.returncode)

            if e.output:
                log_str += LOG_MESSAGES['output'].format(e.output)

            log_output(log_str, level="ERROR", logger=logger, semaphore=semaphore)

            return dcm_dir, False

        finally:

            # Clean up temporary files
            tmp_files = glob(os.path.join(dimon_workdir, "GERT_Reco_dicom*"))
            tmp_files.extend(glob(os.path.join(dimon_workdir, "dimon.files.run.*")))

            if tmp_files:
                list(map(os.remove, tmp_files))

    else:

        raise NiftyConversionFailure("Tool Error: {} is not a supported conversion tool. Please select 'dcm2niix' or "
                                     "'dimon'".format(conversion_tool))


def convert_to_bids(bids_dir, dicom_dir, subject_map=None, conversion_tool='dcm2niix', logger=None,
                    nthreads=MAX_WORKERS, overwrite=False):

    tmp_dir = os.path.join(os.getcwd(), "tmp")

    # If the program is to run in multiple threads, create a Semaphore to be passed into the threads so they can
    # acquire locks if necessary
    if nthreads > 0:
        thread_semaphore = Semaphore(value=1)
    else:
        thread_semaphore = None

    # If BIDS directory exists, verify that it's either empty or that overwrite is allowed. Otherwise create directory.
    if os.path.isdir(bids_dir):

        bids_files = glob(os.path.join(bids_dir, '*'))

        if bids_files:
            if not overwrite:
                raise DuplicateFile("The BIDS directory is not empty and --overwrite is set to False. Aborting.")
            else:
                rm_files = glob(os.path.join(bids_dir, '*'))
                list(map(shutil.rmtree, rm_files))
    else:
        create_path(bids_dir)

    # Get all the compressed file fpaths from the dir containing the dcm tgz files from oxygen/gold
    tgz_fpaths = glob(os.path.join(dicom_dir, "*.tgz"))

    # Iterate through the files, peek at the DICOM files without extracting the whole archive,
    # decide if it is a valid BIDS file, and add to list of files to convert if it is.
    subject_map = OrderedDict()

    if not os.path.isdir(tmp_dir):
        create_path(tmp_dir, thread_semaphore)

    for tgz_file in tgz_fpaths:

        session_dir = extract_tgz(tgz_file, out_path=tmp_dir, logger=logger)

        tgz_fname = tgz_file.split("/")[-1][:-4].split("-")
        subject_id = tgz_fname[1]
        session_id = tgz_fname[2]

        # Get scan dirs
        scan_dirs = glob(os.path.join(session_dir, "mr_*"))

        # Take one dcm file in the dir, check whether scan is of BIDS type, if
        # so, add to map
        for scan_dir in scan_dirs:

            dcm_file = glob(os.path.join(scan_dir, "*.dcm"))[0]

            dcm = dicom.read_file(dcm_file)

            results = get_modality(dcm[0x08, 0x103e].value)

            if results:

                if subject_id not in subject_map.keys():
                    subject_map[subject_id] = OrderedDict()

                if session_id not in subject_map[subject_id].keys():
                    subject_map[subject_id][session_id] = OrderedDict()

                bids_type = results[0]
                modality = results[1]

                if bids_type not in subject_map[subject_id][session_id].keys():
                    subject_map[subject_id][session_id][bids_type] = []

                curr_run = len(subject_map[subject_id][session_id][bids_type])
                nxt_run = "0{}".format(curr_run + 1)  # BUG - THIS WILL BREAK IF MORE THAN 9 RUNS

                if bids_type == "anat":
                    subject_map[subject_id][session_id][bids_type].append([scan_dir, bids_type, modality, nxt_run])
                elif bids_type == "func":
                    task = results[2]  # BUG IN THE COUNTING, WILL NOT COUNT CORRECTLY IF MULT TASKS
                    subject_map[subject_id][session_id][bids_type].append([scan_dir, bids_type, modality, task, nxt_run])

    exec_map = OrderedDict()
    subject_counter = 0
    for subject in subject_map.keys():
        subject_counter += 1
        bids_subject = "sub-0{}".format(subject_counter)

        session_counter = 0
        for session in subject_map[subject].keys():
            session_counter += 1
            bids_session = "ses-0{}".format(session_counter)

            for bids_type in subject_map[subject][session].keys():

                if bids_type == "anat":

                    for run in subject_map[subject][session][bids_type]:

                        modality = run[2]
                        curr_run = run[3]
                        bids_name = "{}_{}_run-{}_{}".format(bids_subject, bids_session, curr_run, modality)
                        scan_bdir = os.path.join(bids_dir, bids_subject, bids_session, bids_type)
                        scan_fpath = run[0]
                        exec_map[bids_name] = (scan_bdir, scan_fpath)

                elif bids_type == "func":

                    for run in subject_map[subject][session][bids_type]:
                        modality = run[2]
                        curr_run = run[4]
                        task = run[3]
                        bids_name = "{}_{}_task-{}_run-{}_{}".format(bids_subject, bids_session, task, curr_run, modality)
                        scan_bdir = os.path.join(bids_dir, bids_subject, bids_session, bids_type)
                        scan_fpath = run[0]
                        exec_map[bids_name] = (scan_bdir, scan_fpath)

    #######################################################
    # DO THIS IF SUBJECT MAP IS PRESENT - NOT WORKING ATM #
    #######################################################

    # Iterate through the subject map and generate the bids names and filepaths for each DICOM series to be converted
    # with open(subject_map, "r") as sm:
    #     subject_map = json.loads(sm.read())
    #
    # exec_map = {}
    #
    # for subject in subject_map.keys():  # Iterates through the subjects
    #
    #     subject_name = subject[4:]
    #
    #     for session in subject_map[subject].keys():  # Iterates through the sessions
    #
    #         session_name = session[4:]
    #
    #         session_fpath = subject_map[subject][session]['session_fpath']
    #
    #         if session_fpath[-4:] == ".tgz":
    #             # Verify file exists
    #
    #             if not os.path.isdir(tmp_dir):
    #                 create_path(tmp_dir, thread_semaphore)
    #
    #             # Extract file into tmp dir and get session_dir
    #             session_dir = extract_tgz(session_fpath, out_path=tmp_dir, logger=logger)
    #
    #         else:
    #             # Verify dir exists
    #             # Assume fpath is a session dir
    #             session_dir = session_fpath
    #
    #         for scan_type in subject_map[subject][session]['scan_types'].keys():
    #
    #             if scan_type == "anat":
    #
    #                 for anat_scan in subject_map[subject][session]['scan_types']['anat']:
    #                     # Extract the run metadata
    #                     scan_dir = anat_scan['scan_dir']
    #
    #                     modality = anat_scan['modality']
    #                     run = anat_scan['run']
    #                     acq = anat_scan.get('acq_label', None)
    #                     rec = anat_scan.get('rec_label', None)
    #
    #                     # Construct the appropriate BIDS name for the current scan
    #                     acq_label = "_acq-{}".format(acq) if acq else ""
    #                     rec_label = "_rec-{}".format(rec) if rec else ""
    #
    #                     bids_name = "sub-{}_ses-{}{}{}_run-{}_{}".format(subject_name, session_name, acq_label,
    #                                                                      rec_label, run, modality)
    #
    #                     # Construct the fpath for the bids directory of the current image, and the fpath for the
    #                     # location of the DICOM data for the current scan
    #                     scan_bdir = os.path.join(bids_dir, "sub-{}".format(subject_name), "ses-{}".format(session_name),
    #                                              "anat")
    #                     scan_fpath = os.path.join(session_dir, scan_dir)
    #
    #                     # Add this data to the list of bids files to be created
    #                     exec_map[bids_name] = (scan_bdir, scan_fpath)
    #
    #             elif scan_type == "func":
    #
    #                 for func_scan in subject_map[subject][session]['scan_types']['func']:
    #                     # Extract the run metadata
    #                     scan_dir = func_scan['scan_dir']
    #
    #                     modality = func_scan['modality']
    #                     task = func_scan['task']
    #                     run = func_scan['run']
    #                     acq = func_scan.get('acq_label', None)
    #                     rec = func_scan.get('rec_label', None)
    #
    #                     # Construct the appropriate BIDS name for the current scan
    #                     acq_label = "_acq-{}".format(acq) if acq else ""
    #                     rec_label = "_rec-{}".format(rec) if rec else ""
    #
    #                     bids_name = "sub-{}_ses-{}_task-{}{}{}_run-{}_{}".format(subject_name, session_name, task,
    #                                                                              acq_label, rec_label, run, modality)
    #
    #                     # Construct the fpath for the bids directory of the current image, and the fpath for the
    #                     # location of the DICOM data for the current scan
    #                     scan_bdir = os.path.join(bids_dir, "sub-{}".format(subject_name), "ses-{}".format(session_name),
    #                                              "func")
    #                     scan_fpath = os.path.join(session_dir, scan_dir)
    #
    #                     # Add this data to the list of bids files to be created
    #                     exec_map[bids_name] = (scan_bdir, scan_fpath)
    #
    #             elif scan_type == "dwi":
    #
    #                 for dwi_scan in subject_map[subject][session]['scan_types']['dwi']:
    #                     # Extract the run metadata
    #                     scan_dir = dwi_scan['scan_dir']
    #
    #                     run = dwi_scan['run']
    #                     acq = dwi_scan.get('acq_label', None)
    #
    #                     # Construct the appropriate BIDS name for the current scan
    #                     acq_label = "_acq-{}".format(acq) if acq else ""
    #
    #                     bids_name = "sub-{}_ses-{}{}_run-{}_dwi".format(subject_name, session_name, acq_label, run)
    #
    #                     # Construct the fpath for the bids directory of the current image, and the fpath for the
    #                     # location of the DICOM data for the current scan
    #                     scan_bdir = os.path.join(bids_dir, "sub-{}".format(subject_name), "ses-{}".format(session_name),
    #                                              "dwi")
    #                     scan_fpath = os.path.join(session_dir, scan_dir)
    #
    #                     # Add this data to the list of bids files to be created
    #                     exec_map[bids_name] = (scan_bdir, scan_fpath)
    #
    #             elif scan_type == "fmap":
    #
    #                 for fmap_scan in subject_map[subject][session]['scan_types']['fmap']:
    #                     # Extract the run metadata
    #                     scan_dir = fmap_scan['scan_dir']
    #
    #                     modality = fmap_scan['modality']
    #                     run = fmap_scan['run']
    #                     acq = fmap_scan.get('acq_label', None)
    #
    #                     # Construct the appropriate BIDS name for the current scan
    #                     modality = "{}_epi".format(modality) if "dir-" in modality else modality
    #                     acq_label = "_acq-{}".format(acq) if acq else ""
    #
    #                     bids_name = "sub-{}_ses-{}{}_run-{}_{}".format(subject_name, session_name, acq_label, run,
    #                                                                    modality)
    #
    #                     # Construct the fpath for the bids directory of the current image, and the fpath for the
    #                     # location of the DICOM data for the current scan
    #                     scan_bdir = os.path.join(bids_dir, "sub-{}".format(subject_name), "ses-{}".format(session_name),
    #                                              "fmap")
    #                     scan_fpath = os.path.join(session_dir, scan_dir)
    #
    #                     # Add this data to the list of bids files to be created
    #                     exec_map[bids_name] = (scan_bdir, scan_fpath)
    #
    # Iterate through executable list and convert to Nifti

    if nthreads > 0:    # Run in multiple threads

        futures = []

        with ThreadPoolExecutor(max_workers=nthreads) as executor:

            for bids_fname, fpaths in exec_map.items():

                dcm_fpath = fpaths[1]
                bids_fpath = fpaths[0]

                futures.append(executor.submit(dcm_to_nifti, dcm_dir=dcm_fpath, out_fname=bids_fname,
                                               out_dir=bids_fpath, conversion_tool=conversion_tool, bids_meta=True,
                                               logger=logger, semaphore=thread_semaphore))
                # FOR TESTING
                # break
                #######

            wait(futures)

            for future in futures:
                dcm_dir, success = future.result()

                if not success:
                    log_output("Could not convert DICOM series in {}".format(dcm_dir), semaphore=thread_semaphore)

    else:   # Run sequentially

        for bids_fname, fpaths in exec_map.items():

            dcm_fpath = fpaths[1]
            bids_fpath = fpaths[0]

            dcm_dir, success = dcm_to_nifti(dcm_dir=dcm_fpath, out_fname=bids_fname, out_dir=bids_fpath,
                                            conversion_tool='dcm2niix', bids_meta=True, logger=logger)

            if not success:
                log_output("Could not convert DICOM series in {}".format(dcm_dir))

    # Print map to csv
    with open(os.path.join(dicom_dir, "bids_map.csv"), "w") as f:

        f.write("bids_subject,bids_session,modality,task,run,dicom_folder\n")

        for bids_fname, fpaths in exec_map.items():

            dcm_fpath = fpaths[1]

            bids_subject = bids_fname.split("_")[0]
            bids_session = bids_fname.split("_")[1]
            modality = bids_fname.split("_")[-1]
            dicom_folder = dcm_fpath
            run = bids_fname.split("_")[-2]
            if modality == "bold" or modality == "sbref":
                task = bids_fname.split("_")[-3]
            else:
                task = ""
            out_str = "{},{},{},{},{},{}\n".format(bids_subject, bids_session, modality, task, run, dicom_folder)
            f.write(out_str)


    # Remove tmp dir if it was created
    if os.path.isdir(tmp_dir):
        shutil.rmtree(tmp_dir)
