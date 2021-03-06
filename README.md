<h3>FMRIF TOOLS</h3>

The <b>fmrif_tools</b> package contains a set of python utilities to aid in the processing and manipulation of scanner
data stored in the Gold and Oxygen archive systems at the Functional Magnetic Resonance Imaging Facility (FMRIF) at
the National Institutes of Health. The utilities run under either Python 2.7+ or Python 3.5+.

<h4>Current utilities:</h4>

<ul>
 <li>
    <b>oxy2bids</b> - A utility to convert DICOM scans downloaded from Gold and Oxygen into a BIDS compatible directory
    directory structure
 </li>
 <li>
    <b>biounpack</b> - A utility to extract physiological recording data from biopack files and save it
    as independent respiratory, cardiac, and trigger 1D data files.
 </li>
  <li>
    <b>dcmexplorer</b> - A utility to parse DICOM files from Oxygen and Gold servers and explore their tags based
    on a user-provided DICOM tag specification file.
 </li>
  <li>
    <b>bidsmapper</b> - A utility to generate a DICOM to BIDS mapping file from a set of Oxygen/Gold archives based 
    on user-provided heuristics and DICOM tags.
 </li>
</ul> 

For usage instructions, please read the full documentation at:

http://fmrif-tools.readthedocs.io/en/latest/
  
For more information, or assistance, contact the lead developer at: 

* jan.varada -at- nih -dot- gov

Please submit any bug reports or feature requests at: <a href="https://github.com/nih-fmrif/fmrif_tools/issues">Report bugs or Feature Requests</a>
