# Data

No real people anywhere. Everything below is public reference data or generated from it.

## data/samples/trial_cdiscpilot01.json

The CDISC SDTM/ADaM pilot study converted to compact JSON by `backend/scripts/convert_cdisc.py`: 254 subjects, lab results, vitals, adverse events, medications. The treatment arm is dropped during conversion so nothing can unblind. Educational-use license from CDISC.

## The generated world (`make load`, deterministic, seed 7)

`backend/sourced/generate.py` builds two clinics per patient:

- Memorial General Hospital: a FHIR R4 bundle per subject from the pilot data. One value per test per day.
- Riverside Clinic and Riverside Diagnostics, for 80 of the 254 adults: a central lab report, a two-page progress note, and for half of them a pharmacy medication list fax. Fifty percent of documented adults have one lab panel that exists only in the outside report, and fifty percent have one visit whose weight exists only in the note.
- Sunrise Pediatrics and County Urgent Care: ten children, immunization history split between the two, an allergy for some, asthma for some.

Planted traps, each recorded in the answer key:

| Kind | What | Expected behavior |
|---|---|---|
| gap_fill | the EHR lacks the value; a document has it | the form fills from the document, receipt points at the page |
| unit_trap | weight in pounds, temperature in Fahrenheit, same true value | converted on read; the verifier reports agreement with the EHR |
| conflict | a document carries a wrong weight or a doubled dose | the filler keeps the EHR value; the verifier flags "disagree" with both values and sources |

## data/samples/world_answer_key.json

Written by `make load` and `make data`. For every document: its facts with exact quotes, as the oracle reader returns them. The planted list. Per-visit truth values for every adult. Per-child immunization counts.

## data/samples/world_documents.json

Written by `make data`: patients, identifiers, and the full text of every generated document, for inspection without a database.

## data/raw (not committed)

Raw openFDA downloads from the earlier Day Zero prototype. Not used by Sourced.
