from __future__ import print_function, unicode_literals

import argparse
import numpy as np

from pathlib import Path
from multiprocessing import cpu_count
from multiecho.utils import move_file, get_df
from dask.distributed import wait, Client, LocalCluster


def reorg_multiechoes(df, out_dir, client):

    out_base = Path(out_dir)
    out_base.mkdir(exist_ok=True)

    # Get the uids of each series in the exam
    unique_series_uids = sorted(df['series_uid'].unique())

    invalid_me_series = []
    reorg_files = []
    # Iterate through the different multiecho series
    for curr_series, series_uid in enumerate(unique_series_uids, 1):

        # Build dataframe containing only the slices which belong to the current series
        curr_series_df = df[df['series_uid'] == series_uid]

        # Get basic data about the series from the first row of the current series dataframe
        first_row = curr_series_df.iloc[0]
        num_indices = first_row['num_indices']
        num_slices = first_row['num_slices']
        num_repetitions = first_row['num_repetitions']
        num_echoes = num_indices // num_slices
        series_path = Path(first_row['path']).parent

        # If there are less files than the number of dicoms the series should have,
        # based on the number of echos acquired, the series is incomplete - skip further processing
        expected_num_dicoms = num_indices * num_repetitions

        if len(curr_series_df) < expected_num_dicoms:

            invalid_me_series.append(series_path)

            out_dir = out_base / "multiecho_series_{}_incomplete".format(
                str(curr_series).rjust(2, '0'), str(len(invalid_me_series)).rjust(2, '0'))

            files = [s.path for s in curr_series_df.itertuples()]

            for f in files:
                reorg_files.append(client.submit(move_file, f, out_dir, copy=True))

        else:

            # Compute a 2D-array of slice indexes, where each row contains the indexes that belong
            # to a particular echo
            unique_slice_indexes = sorted(curr_series_df['slice_index'].unique())
            slice_indexes_per_echo = np.reshape(unique_slice_indexes, [num_echoes, num_indices // num_echoes])

            # Iterate through each echo for the current series
            for curr_echo, echo in enumerate(range(0, num_echoes), 1):

                # Get the image slices that belong to the current echo (based on the
                # image slices array built previously)
                curr_echo_slices = curr_series_df[curr_series_df['slice_index'].isin(slice_indexes_per_echo[echo])]

                # If there are duplicated image files, as has been happening lately when archiving the data,
                # there will be multiple images with different dicom names, but with the same instance_uid
                # numbers. Filter those out by selecting only images with unique instance uids.
                unique_echo_slices = curr_echo_slices.drop_duplicates(subset=['instance_uid'])

                out_dir = out_base / "multiecho_series_{}_echo_{}".format(
                    str(curr_series).rjust(2, '0'), str(curr_echo).rjust(2, '0')
                )

                files = [s.path for s in unique_echo_slices.itertuples()]

                for f in files:
                    reorg_files.append(client.submit(move_file, f, out_dir, copy=True))

    _ = wait(reorg_files)

    return invalid_me_series


def run_sorter(work_dir, out_dir, n_workers=None, dir_type='series'):

    if not n_workers:
        n_workers = cpu_count() - 1

    cluster = LocalCluster(n_workers=n_workers)

    client = Client(cluster)

    if dir_type == 'series':

        df, me_series, non_me_series = get_df(str(work_dir), is_exam_dir=False)

    elif dir_type == 'exam':

        df, me_series, non_me_series = get_df(str(work_dir), is_exam_dir=True)

    else:
        raise(Exception("Unknown directory type."))

    df = df.compute()

    invalid_me_series = reorg_multiechoes(df=df, out_dir=str(out_dir), client=client)

    client.close()
    cluster.close()

    for invalid_me in invalid_me_series:
        if invalid_me in me_series:
            me_series.remove(invalid_me)

    return me_series, invalid_me_series, non_me_series


def run_from_cli():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "work_dir",
        help="Path to an uncompressed work directory.",
    )

    parser.add_argument(
        "out_dir",
        help="Path to base output directory"
    )

    parser.add_argument(
        "--dir_type",
        help="Specify whether the work dir is an exam-level directory or a series-level directory. DEFAULT: 'series'",
        choices=['series', 'exam'],
        default='series'
    )

    parser.add_argument(
        "--n_workers",
        type=int,
        default=cpu_count() - 1
    )

    cli_args = parser.parse_args()

    work_dir = Path(cli_args['work_dir']).absolute()
    out_dir = Path(cli_args['out_dir']).absolute()
    n_workers = int(cli_args['n_workers'])
    dir_type = cli_args['dir_type']

    me_series, invalid_me_series, non_me_series = run_sorter(work_dir=work_dir, out_dir=out_dir,
                                                             n_workers=n_workers, dir_type=dir_type)

    print("Number of multiecho series converted: {}".format(len(me_series)))
    print("Number of invalid multiecho series: {}".format(len(invalid_me_series)))
    print("Number of non-multiecho series: {}".format(len(non_me_series)))


if __name__ == "__main__":
    run_from_cli()
