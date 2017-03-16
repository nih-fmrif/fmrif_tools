BIDS_ANAT = [
    "T1w",  # T1 weighted
    "T2w",  # T2 weighted
    "T1map",  # Quantitative T1 map
    "T2map",  # Quantitative T2 map
    "FLAIR",  # FLAIR
    "FLASH",  # FLASH
    "PD",  # Proton Density
    "PDT2",  # Combined PD / T2
    "inplaneT1",  # T1 - weighted anatomical image matched to functional acquisition
    "inplaneT2",  # T2 - weighted anatomical image matched to functional acquisition
    "angio",  # Angiography
    "defacemask",  # Mask used for defacing
    "SWImageandphase",  # Magnitude and correspodning pohase images of the SWI
]

BIDS_FUNC = [
    'bold',  # BOLD EPI Scan
    'sbref',  # Single-band reference file for multi-band acquisitions
]

BIDS_DWI = [
    'dwi',
]

BIDS_FMAP = [
    "phasediff(num?)",
    "phase(num?)",
    "frequency",
    "magnitude(num?)",
    "fieldmap",
    "dir-<index>",
]
