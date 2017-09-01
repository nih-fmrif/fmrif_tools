"""
FMRIF TOOLS

"""

from datetime import date

__version__ = '0.1b1'

__author__ = 'Jan Varada'

__email__ = 'jan.varada@nih.gov'

__copyright__ = ('Copyright {}, Functional MRI Facility, National Institute of Mental Health, National Institutes of '
                 'Health'.format(date.today().year))

__license__ = '3-clause BSD'

__description__ = 'Tools to perform common task with data generated at the FMRIF facility at the NIH'

__longdesc__ = ('This package contains tools to perform common tasks with the data generated at the Functional'
                'Magnetic Resonance Imaging Facility at the National Institutes of Health. One of the tools, '
                'oxygen2bids, will convert compressed files from the Oxygen database server into BIDS format for '
                'downstream processing with BIDS Tools packages and docker containers.')

__url__ = 'http://fmrif-tools.readthedocs.io/en/latest/'

__download__ = 'https://github.com/nih-fmrif/fmrif_tools/archive/{}.zip'.format(__version__)

PACKAGE_NAME = 'fmrif_tools'

CLASSIFIERS = [
    'Development Status :: 4 - Beta',
    'Intended Audience :: Science/Research',
    'Topic :: Scientific/Engineering :: Interface Engine/Protocol Translator',
    'License :: OSI Approved :: BSD License',
    'Programming Language :: Python :: 3.6',
    'Programming Language :: Python :: 3.5',
    'Programming Language :: Python :: 2.7',
]

REQUIRES = [
    'matplotlib == 2.0.2',
    'pandas == 0.20.3',
    'pydicom == 0.9.9',
    'numpy == 1.13.1',
    'bioread == 1.0.4',
]
