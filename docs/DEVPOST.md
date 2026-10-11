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

**Compliance and integration.** Every value on a form carries its receipt, the document, page, and quote, or the FHIR resource. That is the "original source cited and traceable" must-have in Regeneron's site agents outline, and the attributable and original part of ALCOA+ that ICH E6(R3) and FDA's eSource guidance expect. Signing needs a human decision with a reason on every flagged field, and every action lands in an append-only, SHA-256 hash-chained audit trail that can be re-verified on demand, the tamper evidence 21 CFR Part 11 asks of electronic records. It speaks what sites already run: FHIR R4 in, LOINC codes, CDASH forms, an ODM-shaped export an EDC can import, and intake endpoints for what fax servers and EHR exports produce. Regeneron's outline asks for an agent that "acts alone once proven" with the coordinator accountable: the Metrics page is the proof, the sign-off is the accountability.

## How we built it

The model reads. The rules fill and check. The human signs.

- **Reader:** gpt-4.1 under a strict JSON schema. It must quote every value verbatim, and we locate each quote to a page and character span. A photo is transcribed first, then read like text.
- **Ledger on Tiger Data:** a hypertable of facts with compression, a continuous aggregate for the live chart, pgvector for document search.
- **Filler and verifier:** pure Python rules over a small vocabulary of LOINC codes and unit conversions.
- **Test world:** the CDISC SDTM pilot study (254 subjects) plus generated outside-clinic documents, with planted gaps, unit traps, and conflicts recorded in an answer key. A regex extractor is kept as the baseline sites use today.

**Why Tiger Data, and where.** A clinical ledger is time series, relational rows, JSON, and vectors at once, and Tiger Cloud is one Postgres that holds all four. The `facts` table is a TimescaleDB hypertable chunked by `observed_at`, so the filler's "nearest reading to this visit" query touches only the chunks that overlap the window. Trial history is append-mostly, so Tiger's native columnar compression fits it: chunks older than 400 days compress on a policy, segmented by patient, and stay queryable in place (22 of 24 chunks in our load). The live chart is a continuous aggregate, `time_bucket('1 day')` by organization, refreshed incrementally rather than re-counted per page view. Document search is pgvector in the same database, a 384-dimension column under an HNSW index, so "find the fax that mentions this drug" runs beside the joins with no separate vector store. Receipts are JSONB, the audit trail is a second hypertable with a SHA-256 hash chain, and it is all SQL that hospital IT already knows how to secure. The demo runs on Tiger Cloud (PostgreSQL 18, TimescaleDB 2.30, pgvector 0.8).

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

## Did you implement a generative AI model or API in your hack this weekend?

Yes, in one role: the reader. OpenAI gpt-4.1, through the OpenAI API, reads every outside document (faxes, clinic notes, lab reports, pharmacy lists, and photos or scans of them) and returns each clinical fact with a verbatim quote under a strict JSON schema. We locate every quote to a page and character span, convert units, and keep what was written. The same model transcribes images before reading them, and on request writes a structured second opinion on a flagged field: likely cause, confidence, suggested decision, what to verify. Gemini (gemini-3.8-flash) runs the same three jobs behind the same seam and was verified this weekend; Anthropic is supported too. Everything else is deterministic rules: the ledger, the filler, the verifier, the diagnoses, the sign-off, and the audit chain. The model reads; it never fills, decides, or signs, so every value it produces can be checked against the page it quoted.

## Why an agent, not more scripts

Sites already automate the structured part; connectors reach about 17 percent of trial data, and regex scripts patch the rest. A script is written for one layout. Ours reads 74 percent of the facts on the layouts it was written for and under 1 percent on the ones it was not, and a third of real documents are the ones it was not. A model that must quote every value reads 100 percent of both, and because every quote is located, the rules around it can check its work. That is the step up: not a smarter script, but an agent whose output is verifiable, with a human deciding only what disagreed.

## Built with (tags)

Python, FastAPI, Pydantic, psycopg, PostgreSQL, TimescaleDB, Tiger Data, pgvector, React, Vite, Recharts, OpenAI gpt-4.1, FHIR R4, LOINC, CDISC CDASH, CDISC ODM, PyMuPDF, Docker

Repo: https://github.com/AyaanFaisal21/HackRUF26
