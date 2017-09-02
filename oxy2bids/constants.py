LOG_MESSAGES = {
    'start_conversion': "Beginning conversion to BIDS format",
    'start_map': "Beginning generation of DICOM to BIDS map.",
    'gen_map_warning': "WARNING: --gen_map and --bids_map flags specified. Will use existing bids map instead of "
                       "generating one.",
    'gen_map_done': "Map generation complete. Results stored in {}",
    'shutdown': "BIDS conversion complete. Results stored in {}",
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
