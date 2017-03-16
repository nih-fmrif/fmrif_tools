import os
import re
import errno
import tarfile
import multiprocessing

from bids_keys import BIDS_ANAT, BIDS_DWI, BIDS_FMAP, BIDS_FUNC


MAX_WORKERS = multiprocessing.cpu_count() * 5


def log_output(log_str, level="INFO", logger=None, semaphore=None):

    if semaphore:
        semaphore.acquire()

    if logger:

        if level == 'DEBUG':
            logger.debug(log_str)
        elif level == 'WARNING':
            logger.warning(log_str)
        elif level == 'CRITICAL':
            logger.critical(log_str)
        elif level == 'ERROR':
            logger.error(log_str)
        elif level == 'INFO':
            logger.info(log_str)

    else:
        print(log_str)

    if semaphore:
        semaphore.release()


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

def get_task(key):
    pattern = r"^.*[ -_]task-(?P<task>[a-zA-Z]*).*$"
    result_obj = re.search(pattern, key, re.IGNORECASE)
    if result_obj:
        return result_obj.groupdict()['task']
    else:
        return None #### CHANGE THIS TO RETURN EXCEPTION


def is_member(key, lst):
    regexp = r"^.*[ -_]{}(?P<number>[0-9]*)?([ -_].*)?$"
    for item in lst:
        pattern = regexp.format(item)
        result_obj = re.search(pattern, key, re.IGNORECASE)
        if result_obj:
            if item == "bold" or item == "sbref":
                task = get_task(key)
                return item, task
            if hasattr(result_obj, 'groupdict'):
                return "{}{}".format(item, result_obj.groupdict()['number'])
            else:
                return item
    return None


def get_modality(key):

    bids_type = ""
    modality = ""

    result = is_member(key, BIDS_ANAT)
    if result:
        bids_type = "anat"
        modality = result
        return bids_type, modality

    results = is_member(key, BIDS_FUNC)
    if results:
        bids_type = "func"
        modality = results[0]
        task = results[1]
        return bids_type, modality, task

    result = is_member(key, BIDS_DWI)
    if result:
        bids_type = "dwi"
        modality = result
        return bids_type, modality

    result = is_member(key, BIDS_FMAP)
    if result:
        bids_type = "fmap"
        modality = result
        return bids_type, modality

    return None


