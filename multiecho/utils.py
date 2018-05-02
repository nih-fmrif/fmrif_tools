import pandas as pd
import dask.dataframe as dd
import numpy as np
import shutil

from pydicom import dcmread
from pathlib import Path
from dask import delayed


DF_DTYPES = [
    ('path', np.dtype(str)),
    ('num_indices', np.dtype(int)),
    ('num_repetitions', np.dtype(int)),
    ('tr', np.dtype(float)),
    ('num_slices', np.dtype(int)),
    ('slice_index', np.dtype(int)),
    ('series_uid', np.dtype(str)),
    ('instance_uid', np.dtype(str))
]


def move_file(dcm_path, path, copy=False):

    out_path = Path(path)
    out_path.mkdir(exist_ok=True)

    dcm_path = Path(dcm_path)

    if copy:

        shutil.copy2(dcm_path, out_path / dcm_path.name)

    else:

        shutil.move(dcm_path, out_path / dcm_path.name)


def get_me_meta(dcm):

    # 0020, 1002 - No. of Images in Acquisition (no. indices)
    # 0020, 0105 - No. of Temporal Positions
    # 0018, 0080 - Repetition Time (TR)
    # 0021, 104f - No. of Slices
    # 0019, 10a2 - Slice Index
    # 0020, 000E - Series UID
    # 0008, 0018 - Instance UID

    hdr = dcmread(str(dcm), stop_before_pixels=True)

    df_data = {
        'path': [str(dcm)],
        'num_indices': [int(hdr.get([0x0020, 0x1002]).value)],
        'num_repetitions': [int(hdr.get([0x0020, 0x0105]).value)],
        'tr': [float(hdr.get([0x0018, 0x0080]).value)],
        'num_slices': [int(hdr.get([0x0021, 0x104f]).value)],
        'slice_index': [int(hdr.get([0x0019, 0x10a2]).value)],
        'series_uid': [str(hdr.get([0x0020, 0x000E]).value).strip()],
        'instance_uid': [str(hdr.get([0x0008, 0x0018]).value).strip()],
    }

    df = pd.DataFrame.from_dict(df_data, orient='columns')

    return df


def process_series(series_dir):

    non_me_series = []
    me_series = []
    me_dataframes = []

    # 0020, 1002 - No. of Images in Acquisition
    # 0020, 0105 - No. of Temporal Positions
    # 0018, 0080 - Repetition Time (TR)
    # 0021, 104f - No. of Slices

    series = Path(series_dir)

    if series.is_dir():

        for dcm in series.iterdir():

            if dcm.match("*.dcm"):

                hdr = dcmread(str(dcm), stop_before_pixels=True)

                num_indices = hdr.get([0x0020, 0x1002], None)
                num_slices = hdr.get([0x0021, 0x104f], None)

                if not num_indices or not num_slices:
                    non_me_series.append(series)
                else:
                    num_indices = int(num_indices.value)
                    num_slices = int(num_slices.value)

                    if (num_indices != num_slices) and hdr.get([0x0020, 0x0105], None):

                        me_series.append(series)

                        me_dataframes.extend([delayed(get_me_meta)(dicom_file) for dicom_file
                                              in [s for s in series.glob("*.dcm")]])

                    else:

                        non_me_series.append(series)

                break

    return me_dataframes, me_series, non_me_series


def get_df(work_dir, is_exam_dir=False):

    if is_exam_dir:

        exam_dir = Path(work_dir)

        non_me_series = []
        me_series = []
        me_dataframes = []

        for series in exam_dir.iterdir():

            me_df, me_s, non_me_s = process_series(series)

            me_series.extend(me_s)
            non_me_series.extend(non_me_s)
            me_dataframes.extend(me_df)

    else:

        series = Path(work_dir)

        me_dataframes, me_series, non_me_series = process_series(series)

    df = dd.from_delayed(me_dataframes, meta=DF_DTYPES)

    return df, me_series, non_me_series
