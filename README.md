# Sourced

Medical forms that fill themselves, with receipts.

Every trial visit produces data that someone retypes from the hospital record into the sponsor's forms, and someone else checks against the source. Connectors automate the structured part. The one independent multi-sponsor study found that is about 17 percent of trial data points. The rest lives in scanned lab reports, discharge summaries, clinic notes, and medication lists written as prose. Sourced reads those into a ledger where every fact carries its origin, fills forms from the ledger, has a second pass check every field, and lets a human sign only what disagreed.

Built for the Regeneron track at HackRU Fall 2026. Runs on Tiger Data.

## What it does

| Step | Module | How |
|---|---|---|
| Store | `backend/sourced/store.py`, `backend/sql/sourced.sql` | Raw documents kept unchanged with a hash. A ledger of facts, one row per value with concept code, unit, time, source organization, document page and text span or FHIR resource, extractor, confidence. Hypertable on Tiger Data |
| Read, structured | `reader.py` `read_fhir_bundle` | FHIR R4 Patient, Observation (LOINC), MedicationStatement, Condition, AllergyIntolerance, Immunization, AdverseEvent into facts, confidence 1.0 |
| Read, documents | `reader.py` `ModelDocReader` | The model lists every fact with a verbatim quote; the quote is located to a page and span. `OracleDocReader` plays the answer key so the whole system runs with no key |
| Code and convert | `concepts.py` | Small shared vocabulary with LOINC codes, synonyms, fuzzy matching, and unit conversion (pounds, Fahrenheit, mg/dL) |
| Fill | `forms.py` | A form is a list of questions. Each field is a concept, a time window, a unit. The filler answers from the ledger, nearest to the visit first, with a receipt, a confidence, and the other values it saw |
| Verify | `verifier.py` | Independent pass: plausible range, the number inside the quote matches the extracted value, agreement across source organizations, conflicts inside list rows. Optional model second opinion |
| Review | `api.py`, `frontend/` | Queue of filled forms, disagreements first. Accept, choose another source, enter manually, or leave blank, each with a reason. Signing requires every flagged field decided. Export as ODM-shaped JSON. Append-only audit trail |
| Measure | `evaluate.py` | Fill rate, accuracy, receipt coverage, planted conflicts caught, unit traps converted, gaps filled from documents, false alarms, school forms complete across clinics |

Forms included: CDASH Vital Signs, Laboratory, Concomitant Medications, Adverse Events, Demographics, Medical History, and the New Jersey Universal Child Health Record (CH-14) provider section.

## Quickstart

Requirements: Python 3.11+, Node 18+, Docker, or a Tiger Cloud service.

```bash
make setup                 # venv, pip, npm
cp .env.example .env       # local database URL is already there; add a model key for live reading
make db-up                 # local TimescaleDB with pgvector on :5433 (skip if DATABASE_URL points at Tiger Cloud)
make db-init               # ledger schema: hypertables, continuous aggregate, vector index
make load                  # generate the two-clinic world and read every source into the ledger (about 5 seconds locally)
make fill                  # fill and verify forms for 30 documented patients and the 10 children
make api                   # http://localhost:8000/docs
make web                   # http://localhost:5173
```

Then `make eval` writes `docs/eval-sourced-oracle.md`, and `make test` runs the unit tests.

Live document reading: put `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` in `.env`, set `SOURCED_READER=model`, then `make load` and `make eval`. The Ingest panel on the Documents page reads pasted text live with the same key. With no key, documents are read from the answer key and the rest of the system runs unchanged.

## The data

Two clinics per patient, no real people.

- **Memorial General Hospital**, the EHR, as FHIR R4 bundles built from the CDISC SDTM pilot: 254 subjects, labs, vitals, adverse events, medications. Treatment arm removed.
- **Riverside Clinic and Riverside Diagnostics**, the outside records, generated from the same facts: lab reports, two-page progress notes, pharmacy faxes. Planted gaps (a value that exists only in a document), unit traps (pounds, Fahrenheit), and conflicts (a wrong value).
- **Sunrise Pediatrics and County Urgent Care**: ten children with immunization records split across the two, for the school form.
- The answer key is every document's facts with exact quotes, plus the planted list. `make eval` scores against it.

See `data/README.md`.

## Why Tiger Data

| Need | Feature | Where |
|---|---|---|
| A ledger of observations per patient over time, growing every visit | Hypertable `facts` partitioned on observed time, compression policy | `sql/sourced.sql` |
| Facts arriving per source per day | Continuous aggregate `facts_daily` | `store.facts_daily` |
| "Where in this patient's 40 documents is the most recent hemoglobin" | pgvector HNSW index over document chunks | `store.search_chunks` |
| Append-only audit | Hypertable `audit_log` | `store.audit` |
| Patients, identifiers across clinics, forms, decisions | Plain relational tables | `sql/sourced.sql` |

`make compress` compresses ledger chunks older than 120 days and prints the before and after size.

## Rules of the road

Synthetic data only. A human signs every form. The tool fills and checks; it does not diagnose, assess causality, or decide eligibility. A form pulls only the fields it asks for, for the patient it names.

## Sources

- TransFAIR study of EHR2EDC, https://pmc.ncbi.nlm.nih.gov/articles/PMC10277109/
- Monitoring and source data verification cost, https://pmc.ncbi.nlm.nih.gov/articles/PMC4386950/
- FDA, Electronic Source Data in Clinical Investigations, 2013; FDA, Use of Electronic Health Record Data in Clinical Investigations, 2018
- CDISC SDTM/ADaM pilot project (educational use); CDISC CDASH
- New Jersey Universal Child Health Record, https://www.nj.gov/health/forms/ch-14.pdf

## License

MIT. See `LICENSE`.
