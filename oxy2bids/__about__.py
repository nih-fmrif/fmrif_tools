"""
FMRIF TOOLS

"""

from datetime import date

__version__ = '0.1a3'
__author__ = 'Jan Varada'
__email__ = 'jan.varada@nih.gov'
__maintainer__ = 'Jan Varada'
__copyright__ = ('Copyright {}, Functional MRI Facility, National Institute of Mental Health, National Institutes of '
                 'Health'.format(date.today().year))
__credits__ = 'Jan Varada'
__license__ = '3-clause BSD'
__status__ = 'Prototype'
__description__ = 'Tools to perform common task with data generated at the FMRIF facility at the NIH'
__longdesc__ = ('This package contains tools to perform common tasks with the data generated at the Functional'
                'Magnetic Resonance Imaging Facility at the National Institutes of Health. One of the tools, '
                'oxygen2bids, will convert compressed files from the Oxygen database server into BIDS format for '
                'downstream processing with BIDS Tools packages and docker containers.')
__url__ = ''
__download__ = 'https://github.com/nih-fmrif/fmrif_tools/archive/{}.zip'.format(__version__)

PACKAGE_NAME = 'fmrif_tools'

CLASSIFIERS = [
    'Development Status :: 3 - Alpha',
    'Intended Audience :: Science/Research',
    'Topic :: Scientific/Engineering :: Interface Engine/Protocol Translator',
    'License :: OSI Approved :: BSD License',
    'Programming Language :: Python :: 3.5',
    'Programming Language :: Python :: 2.7',
]

REQUIRES = [
    'click==6.6',
    'configparser==3.5.0',
    'decorator==4.0.10',
    'funcsigs==1.0.2',
    'future==0.16.0',
    'futures==3.0.5',
    'isodate==0.5.4',
    'lxml==3.6.4',
    'networkx==1.11',
    'nibabel==2.1.0',
    'nipype==0.13.1',
    'numpy==1.11.2',
    'pandas==0.20.1',
    'prov==1.5.0',
    'pydicom==0.9.9',
    'pyparsing==2.1.10',
    'python-dateutil==2.6.0',
    'pytz==2017.2',
    'rdflib==4.2.1',
    'scipy==0.18.1',
    'simplejson==3.10.0',
    'six==1.10.0',
    'traits==4.6.0',
    'xvfbwrapper==0.2.8',
]
