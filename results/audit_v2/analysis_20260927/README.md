# Completed single-annotator audit

Start with ANALYSIS_REPORT.md. RUBRIC_REVIEW_20260927.md lists observations
without changing the original annotations. Primary and exploratory results
are separate JSON files. Inputs and source code are archived for reproducibility.

From this folder, the primary analysis can be reproduced under a new filename:

`py -B source/analyze_audit_sample.py inputs --allow-single-annotator --output reanalysis.json`

The exploratory counts can be reproduced with:

`py -B source/reproduce_exploratory.py`

The original live annotations were not modified. Preserve this as-collected
archive if any later adjudication or secondary analysis is undertaken.
