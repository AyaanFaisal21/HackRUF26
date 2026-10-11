# Devpost submission text

Tagline: Clinical data that manages itself, with receipts.

## About the project (paste into "Project Story")

## Inspiration

A 400-patient Phase 3 trial produces about 290,000 data points. Each one is typed by a coordinator from a hospital record into the sponsor's forms, then checked against the source by a monitor. That checking is 15 to 30 percent of a trial's cost. Connectors that move structured hospital data into trial databases reach about 17 percent of the data (TransFAIR, BMJ Health & Care Informatics 2023). The rest is faxes, scanned lab reports, and clinic notes. Regeneron's site agents outline names Source-to-EDC as the first data agent to build, with one rule: every value cited and traceable.

## What it does

Sourced is clinical data that manages itself, with receipts.

- **Reads every source.** FHIR from the hospital; text, photos, scans, or PDFs from everywhere else. Every fact keeps its document, page, span, and verbatim quote, or its FHIR resource id.
- **Fills the forms.** CDASH visit pages (demographics, vital signs, labs, medications) and the New Jersey school health record, from one ledger per patient, nearest value to the visit first.
- **Checks every field again.** Plausible range, the quote matches the value, sources agree within three days, no conflicts inside medication rows.
- **Explains every disagreement.** Who recorded what, where, and when; the likely cause (a unit error, transposed digits, a dispensing list that cannot show a stop, a value out of line with the patient's own history); and a suggested decision.
- **A person decides only what was flagged**, signs, and exports ODM-shaped JSON with the receipts inside. Every action lands in an append-only audit trail.

## How we built it

The model reads. The rules fill and check. The human signs.

- **Reader:** gpt-4.1 under a strict JSON schema. It must quote every value verbatim, and we locate each quote to a page and character span. A photo is transcribed first, then read like text.
- **Ledger on Tiger Data:** a hypertable of facts with compression, a continuous aggregate for the live chart, pgvector for document search.
- **Filler and verifier:** pure Python rules over a small vocabulary of LOINC codes and unit conversions.
- **Test world:** the CDISC SDTM pilot study (254 subjects) plus generated outside-clinic documents, with planted gaps, unit traps, and conflicts recorded in an answer key. A regex extractor is kept as the baseline sites use today.

## Challenges we ran into

- Making a model checkable: it must quote, and the locator must find the quote even when whitespace or degree signs are mangled.
- False alarms: same-day duplicate vitals, one-letter labels fuzzy-matched to blood pressure, a single dose with no end date read as "still active". Each one became a rule.
- Staying honest without a key: an oracle reader plays the answer key and cached model reads reproduce every number from a clean clone.

## Accomplishments that we're proud of

On 60 patients and 1,009 fields with a known truth: 100% filled, 100% accurate, every field with a receipt, 35 of 35 planted conflicts caught, 0 false alarms. The reader recalls 100% of facts against 43.9% for the regex baseline, which falls to 0.7% on layouts it was not written for. On the demo forms, structured data alone fills 68% of the fields; with the reader, 99.7%. A photographed fax becomes ten located facts in eight seconds.

## What we learned

The 17 percent ceiling is not a technology limit. It is where the data lives. Free text and other sites hold the rest, and reading them is only useful when every value can be traced back to the page it came from.

## What's next

Connectors for fax servers and EHR document exports, a real EDC export target, scanned PDFs at volume, and the "acts alone once proven" switch from the Regeneron outline: an agent that stops asking about the field types it has been right about.

## Built with (tags)

Python, FastAPI, Pydantic, psycopg, PostgreSQL, TimescaleDB, Tiger Data, pgvector, React, Vite, Recharts, OpenAI gpt-4.1, FHIR R4, LOINC, CDISC CDASH, CDISC ODM, PyMuPDF, Docker

Repo: https://github.com/AyaanFaisal21/HackRUF26
