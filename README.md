<h3>BIDS TAGS</h3>

<b>Anatomical Files:</b>

"T1w",  // T1 weighted
"T2w",  // T2 weighted
"T1map",    // Quantitative T1 map
"T2map",    // Quantitative T2 map
"FLAIR",    // FLAIR
"FLASH",    // FLASH
"PD",   // Proton Density
"PDT2", // Combined PD/T2
"inplaneT1",    // T1-weighted anatomical image matched to functional acquisition
"inplaneT2",    // T2-weighted anatomical image matched to functional acquisition
"angio",    // Angiography
"defacemask",   // Mask used for defacing
"SWImageandphase"   // Magnitude and correspodning pohase images of the SWI

<b>Functional Files:</b>

"bold",     // BOLD EPI scans
"sbref"     // Single-band reference file for multiband acquisitions

* For functional tasks, also add task name as follows: "task-<name>"

<b>DTI Files:</b>

"multiband"

<b>Fieldmap Files:</b>

"phase(num?)",
"phasediff(num?)",
"frequency", 
"magnitude(num?)",
"fieldmap",
"dir-<index>"