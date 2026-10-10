# Protocol Pre-Flight spike

Goal: test the one known roadblock, Schedule of Activities (SoA) extraction from real protocol PDFs, and prove the endpoint-to-SoA check end to end.

## What runs
```
../../.venv/bin/python -I spike.py              # naive text and pdfplumber table extraction (fails, kept as evidence)
../../.venv/bin/python -I soa_parser.py         # coordinate-based parser: snaps each X to the nearest header column
../../.venv/bin/python -I check_endpoint_soa.py # endpoint timepoint must exist in SoA; then injects a defect
```
Protocols in `data/` come from the ClinicalTrials.gov v2 API (`documentSection.largeDocumentModule`): Lilly dulaglutide (NCT03495102), Lilly tirzepatide (NCT03131687), Janssen canagliflozin (NCT02065791).

## Findings
- Naive approaches fail on all three. Text extraction keeps the rows but loses which column each X sits in. pdfplumber's table extraction returns 15-column grids with empty header cells.
- The coordinate parser works on the Lilly template. It reads the "Week of Treatment" header row, takes the x-center of every numeric token as a column, then assigns every X mark on every activity row to the nearest column. Dulaglutide: 50 activity rows, HbA1c at weeks -2, 1, 8, 12, 26, 36, 52, 56. Tirzepatide: 35 rows, HbA1c at 10 visits.
- The endpoint-to-SoA check passes on both real Lilly protocols (primary endpoint HbA1c at Week 36 and at Week 26 both have a matching SoA column). Deleting the endpoint week from the HbA1c row produces a CRITICAL finding with passage A, passage B, and a fix sentence. That is the Better-tier core, demonstrated on real documents with no LLM.
- The Janssen template breaks the parser. Headers wrap across three lines ("Week 52 / and at 26- / week intervals"), activity labels wrap ("Informed / for optional"), and only 5 of roughly 12 columns were recovered. The sheet's own warning about PDF parsing is real for this family of templates.
- A first false positive came from my own page range (the tirzepatide HbA1c row is on page 15, the spike parsed 12 to 14). Lesson: detect the SoA page span automatically by repeating header rows, do not hardcode it.

## Roadblocks and mitigations
1. SoA layout variance. Plan: coordinate parser for sponsor templates with a single header row, Claude vision on the rendered page image as the fallback, and a CSV upload as the escape hatch. Report which path was used on every protocol.
2. Duplicate week columns (tirzepatide has two visits in weeks 1, 2, 4, 12). Key columns by visit number and carry week as an attribute.
3. Footnote superscripts attach to X marks ("Xe", "Xt"). Handled with a regex, but footnotes change meaning ("only if..."), so surface them as evidence.
4. Endpoint extraction is still a hand transcription in `check_endpoint_soa.py`. It needs the LLM step, and no API key was available here.

## Next build steps
1. Auto-detect SoA page span, key on visit numbers, keep footnote letters.
2. LLM extraction of objectives and endpoints into `{measure, week, source_page, quote}`.
3. Numeric consistency checks (age range, dose, duration) across synopsis, eligibility, and body sections.
4. Defect injector operating on the parsed structure plus the PDF text, with an answer key and a precision and recall table.
