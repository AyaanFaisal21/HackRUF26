# Sourced

Clinical data that manages itself, with receipts.

Every trial visit produces data that someone retypes from the hospital record into the sponsor's forms, and someone else checks against the source. Connectors automate the structured part. The one independent multi-sponsor study found that is about 17 percent of trial data points. The rest lives in scanned lab reports, discharge summaries, clinic notes, and medication lists written as prose. Sourced reads those into a ledger where every fact carries its origin, fills forms from the ledger, has a second pass check every field, says what probably caused each disagreement, and lets a human sign only what disagreed. Paper comes in as text, a photo, a scan, or a PDF.

Built for the Regeneron track at HackRU Fall 2026. Runs on Tiger Data.

## What it does

| Step | Module | How |
|---|---|---|
| Store | `backend/sourced/store.py`, `backend/sql/sourced.sql` | Raw documents kept unchanged with a hash. A ledger of facts, one row per value with concept code, unit, time, source organization, document page and text span or FHIR resource, extractor, confidence. Hypertable on Tiger Data |
| Read, structured | `reader.py` `read_fhir_bundle` | FHIR R4 Patient, Observation (LOINC), MedicationStatement, Condition, AllergyIntolerance, Immunization, AdverseEvent into facts, confidence 1.0 |
| Read, documents | `reader.py` `ModelDocReader` | The model lists every fact with a verbatim quote; the quote is located to a page and span. `OracleDocReader` plays the answer key so the whole system runs with no key |
| Read, paper | `api.py` `/api/documents/upload` | A photo, scan, or PDF is transcribed by the model first, then read like any text. The receipts point into the transcription and the original is kept beside it. The reader also names the document kind and date when they are not given |
| Code and convert | `concepts.py` | Small shared vocabulary with LOINC codes, synonyms, fuzzy matching, and unit conversion (pounds, Fahrenheit, mg/dL) |
| Fill | `forms.py` | A form is a list of questions. Each field is a concept, a time window, a unit. The filler answers from the ledger, nearest to the visit first, with a receipt, a confidence, and the other values it saw |
| Verify | `verifier.py` | Independent pass: plausible range, the number inside the quote matches the extracted value, agreement across source organizations, conflicts inside list rows. Every flag comes with a plain-language sentence built from the receipts: who recorded what, where, and when. Every disagreement gets a likely cause and a suggested decision from rules: unit arithmetic (a 67 that is really pounds), transposed digits, a decimal slip, the patient's own history, a dispensing list that cannot show a stop. The coordinator decides; the model can be asked for its own reading of the receipts |
| Review | `api.py`, `frontend/` | Queue of filled forms, disagreements first. Each flagged field or row shows why it is flagged, every source with its document page and quote, and on request a model explanation that reasons only from those receipts (stored on the field, audited). Accept, choose another source, enter manually, or leave blank, each with a reason. Signing requires every flagged field decided. Export as ODM-shaped JSON that carries the audit chain head. Append-only audit trail where every event is SHA-256 hashed with the one before it; `GET /api/audit/verify` recomputes the chain and names the first event that no longer holds |
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

**Model reading.** Put `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, or `GEMINI_API_KEY` in `.env` and set `SOURCED_READER=model`. All three providers sit behind one seam in `llm.py` (structured output, text, and image transcription); with several keys the order is Anthropic, OpenAI, Gemini, and `LLM_PROVIDER` forces one. Gemini was verified on 2026-10-11 with `gemini-3.8-flash`: the same six facts from the pharmacy fax, all located, and a correct transcription of the photographed note. `make load` then has the model read every document, with 8 concurrent requests, and caches each read in `data/samples/model_reads.json` keyed by the document's hash, so later loads (and the Tiger Cloud load) reuse them for free. The committed cache holds the gpt-4.1 reads, so `make load` with `SOURCED_READER=model` reproduces the published numbers without a key. The Ingest panel on the Documents page reads pasted text live. With no key and no cache, documents are read from the answer key and the rest of the system runs unchanged.

## Results

From `docs/eval-sourced-model.md`, 60 patients, 1,022 form fields with a known truth, 208 documents with 1,669 answer-key facts:

| Forms | |
|---|---|
| Fields filled automatically | 100% |
| Accuracy of filled fields | 100% |
| Filled fields with a receipt | 100% |
| Planted conflicts caught by the verifier | 35 of 35 |
| Unit traps (pounds, Fahrenheit) converted correctly | 12 of 12 |
| Gaps filled from an outside document | 32 of 32 |
| False alarms | 0 |
| School forms with immunizations complete across two clinics | 10 of 10 |

| Document reading, against the answer key | Scripts baseline | Model reader (gpt-4.1) |
|---|---|---|
| Recall, all documents | 43.9% | 100% |
| Recall, layouts the scripts were written for | 74.1% | 100% |
| Recall, layouts they were not (a third of the documents) | 0.7% | 100% |
| Precision | 100% | 99.2% |
| Quotes located to a page and span | n/a | 100% |

The scripts baseline is a real regex extractor in `reader.py`, written for these document layouts. The documents are clean synthetic text, not scans, so these are upper bounds for reading; the form, verifier, and receipt numbers do not depend on that.

## The data

Two clinics per patient, no real people.

- **Memorial General Hospital**, the EHR, as FHIR R4 bundles built from the CDISC SDTM pilot: 254 subjects, labs, vitals, adverse events, medications. Treatment arm removed.
- **Riverside Clinic and Riverside Diagnostics**, the outside records, generated from the same facts: lab reports, two-page progress notes, pharmacy faxes. A third use alternate layouts (abbreviations like "B/P" and "Wt.", reordered columns, date-first vaccine cards). Planted gaps (a value that exists only in a document), unit traps (pounds, Fahrenheit), and conflicts (a wrong weight, a doubled dose).
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
