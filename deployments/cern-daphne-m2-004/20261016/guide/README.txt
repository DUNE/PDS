DAPHNE-M2-004 CERN handoff — revision 1, 16 October 2026

Start with daphne-m2-004-guide.pdf.
Edit report-template.tex for a future scan report; report-template.pdf is its preview.

The guide contains the deployment report, registered and actual network
addresses, gateware selector commands, firmware/physical channel mapping,
DAPHNE+SSP scan configuration, a repeat procedure, measured run-45371 results,
reporting guidance, and qualification limits.

Build from this directory:
  tectonic daphne-m2-004-guide.tex
  tectonic report-template.tex
Alternatively use a LaTeX installation supplying the packages named in the
sources, running pdflatex twice for contents and cross-references.

figures/ contains the exported pedestal/RMS plot in PDF and PNG.
evidence/ contains numeric analysis, source/input hashes, the executed plan
and journal, DNS and DAQ-stop logs, and the initial deployment record.
The initial deployment record concerns earlier run45368; the final quantitative
result is run45371, joint-gain-r4, in evidence/evidence.json and analysis.json.

support/ archives the exact executed runner, wire-ID acquisition adapter,
SSP driver/routine, decoder, original cached environment, and base plan.
This code depends on the installed CERN PDS/DAQ/CVMFS environment and original
campaign paths. It is not a standalone DAQ distribution. Never unpack it over a
live campaign. Follow the guide's fresh-tag procedure to repeat a scan.

The archived decoder intentionally refuses to overwrite its existing analysis
directory. Copy and adapt it to new paths and run metadata for another run.
Large raw HDF5 and waveform .bin files are NOT included; their original CERN
paths and SHA-256 values are recorded in the receipts/evidence.

The measurement exercises control and data acquisition on separate timing
masters. It does not demonstrate optical response, physical detector gain,
or shared-master synchronization. No new hardware run was launched while
preparing this documentation.

manifest.json records this handoff's file hashes and provenance.
