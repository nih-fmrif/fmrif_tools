import os
import errno
import tarfile
import multiprocessing


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
    scans_folder = tar.next().name
    tar.extractall(path=out_path)
    tar.close()

    extracted_dir = "{}"

    if out_path == ".":
        extracted_dir = extracted_dir.format(os.path.join(os.getcwd(), scans_folder))
    else:
        extracted_dir = extracted_dir.format(os.path.join(out_path, scans_folder))

    log_output("Extracted file {} to {} directory.".format(fpath, extracted_dir), logger=logger, semaphore=semaphore)

    return extracted_dir
