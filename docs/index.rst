.. FMRIF Tools documentation master file, created by
   sphinx-quickstart on Wed Jun  7 10:28:39 2017.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to FMRIF Tools's documentation!
=======================================

************
Introduction
************

    The **fmrif_tools** package contains a set of python utilities to aid in the processing and manipulation of scanner
    data stored in the Gold and Oxygen archive systems at the Functional Magnetic Resonance Imaging Facility (FMRIF) at
    the National Institutes of Health. The utilities run under either Python 2.7+ or Python 3.5+.

    Current utilities:
        * **oxy2bids** - A utility to convert DICOM scans downloaded from Gold and Oxygen into a BIDS compatible directory
          directory structure

    For more information, or assistance, contact the lead developer at:
        ``jan.varada -at- nih -dot- gov``

    Please submit any bug reports or feature requests at `Report bugs or Feature Requests <https://github.com/nih-fmrif/fmrif_tools/issues>`_.


************
Installation
************

==============
Pre-requisites
==============
    #. **dcm2niix**
           Needed for the **oxy2bids** utility. It must be accessible in the system's **PATH** variable. See
           `dcm2niix Installation Instructions <https://www.nitrc.org/plugins/mwiki/index.php/dcm2nii:MainPage>`_ for
           installation instructions.
    #. **Python 2.7+** or **Python 3.5+**
           I recommend installing **Anaconda**, as this will also include a way to manage virtual environments to
           prevent python packages from polluting the system-wide Python installation. See
           https://www.continuum.io/downloads for download and installation instructions. **The rest of this guide
           assumes you are using Anaconda's Python installation, although other setups (e.g. via virtualenv) are
           possible.**
    #. **git**
           Needed for pip to extract the package contents from Github. See https://git-scm.com/downloads for download
           and installation instructions.


=====
Setup
=====

    #. If a suitable virtual environment has not been created, create one. For this example we'll call our environment **fmrif_tools**:
           ``conda create -n fmrif_tools python=3 -y``
    #. Activate the virtual environment created in the step above:
           ``source activate fmrif_tools``
    #. Install the fmrif_tools package from github:
           ``pip install git+https://github.com/nih-fmrif/fmrif_tools.git``
    #. The utility is now ready to use from the command line (or terminal), e.g.,
          ``oxy2bids [options] ...``
    #. To exit the virtual environment once you are done using the utility, type
          ``source deactivate``

    * To use re-activate the virtual environment to use in a later session, simply type,
          ``source activate <virtual environment name>``

      as in step 2 above. The package should be ready to use again.


********
oxy2bids
********

============
Introduction
============

    **oxy2bids** is a python utility that takes in a series of DICOM scans from Oxygen, generates an intermediate csv file
    containing a mapping of DICOM scans to BIDS hierarchy, and then converts the scans to the appropriate BIDS hierarchy. It
    uses **dcm2niix** behinds the scenes to convert the DICOM scans to NIFTI format. Support for AFNI's **Dimon** DICOM to NIFTI
    conversion tool will be implemented in the near future.

=====
Usage
=====

    * At a minimum, a folder containing the Oxygen/Gold files to be parsed and extracted is needed.
    * **NOTE: At the moment, oxy2bids requires the original, uncompressed files downloaded from Oxygen/Gold.**

        * Example:

            Suppose we want to create a BIDS hierarchy from two Oxygen files, DOE_JOHN-12345-20170101-56789-DICOM.tgz
            and DOE_JANE-23456-20160101-56789-DICOM.tgz. The files should be located in a common directory, say
            *oxygen_data*, and the filesystem hierarchy should look as follows::

                oxygen_data/
                    DOE_JOHN-12345-20170101-56789-DICOM.tgz
                    DOE_JANE-23456-20160101-56789-DICOM.tgz

-----------------------
Basic Command and Flags
-----------------------

    * The basic command structure of **oxy2bids** is as follows,
          ``oxy2bids [options] <dicom data directory>``

    * The following **options** are allowed:

        **--auto**
            Automatically generates a BIDS hierarchy based on input DICOM files, assuming the
            generated BIDS mapping is correct. Not recommended. Default: False.
        **--gen_map**
            Generate a DICOM to BIDS map, which can be then verified and fined tuned as necessary
            prior to conversion of the oxygen/gold datasets into a BIDS-structured dataset. Default: True.
        **--bids_dir**
            Path to desired top-level output directory of BIDS-formatted dataset. If not specified,
            a directory called **bids_data_<timestamp>** will be created in the current working directory.
        **--bids_map**
            Path to a preexisting DICOM to BIDS mapping file. Overrides **--gen_map** option.
        **--log_filepath**
            Path to the log file. Default will be a file named **oxy2bids_<timestamp>.log** in the current
            working directory.
        **--conversion_tool**
            Specify the tool that will convert DICOM series into NIFTI files. Note that at the present time,
            only **dcm2niix** is supported. Default: dcm2niix.
        **--overwrite**
            If files exist in BIDS data folder, overwrite them. **Note: Not implemented yet.** Default: False.
        **--nthreads**
            Number of threads the program should use when parsing the DICOM files and generating the BIDS dataset.
        **--debug**
            Outputs useful information for debugging to the log and console.

    * For more information on how to combine these flags, see the supported use cases in the following sections.

-------------------------------------------------------------------------------------------------------------------------------------------
Use Case 1 (Recommended) - Generate a BIDS mapping file, manually inspect it and correct it, then generate BIDS tree based on generated map
-------------------------------------------------------------------------------------------------------------------------------------------

---------------------------------------------------------------------------------------------------------
Use Case 2 - Pass in a pre-generated BIDS mapping file, generate the BIDS tree based on the given mapping
---------------------------------------------------------------------------------------------------------

----------------------------------------------------------------------------------------------------------------------------
Use Case 3 (Not Recommended) - Assume BIDS mapping generated by oxy2bids will be correct, generate the BIDS tree based on it
----------------------------------------------------------------------------------------------------------------------------




==============
Advanced Usage
==============

----------------------------------------
Query DICOM datasets for custom keywords
----------------------------------------


*******
License
*******

Copyright (c) 2017, the Functional Magnetic Resonance Imaging Facility (FMRIF) at the National Institute of Mental Health,
National Institutes of Health.

All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice, this
  list of conditions and the following disclaimer.

* Redistributions in binary form must reproduce the above copyright notice,
  this list of conditions and the following disclaimer in the documentation
  and/or other materials provided with the distribution.

* Neither the names of fmrif_tools, oxy2bids, nor the names of its
  contributors may be used to endorse or promote products derived from
  this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
