# Sourced: medical forms that fill themselves, with receipts

Working name. Change it if you find a better one.

## The pitch

**Seven words.** Medical forms that fill themselves, with receipts.

**Thirty seconds.** Everyone has filled a form that asks for information that already exists somewhere. A clipboard at the doctor. A school health form. A clinical trial visit form. Someone hunts through records in three systems and a stack of faxes, retypes the values, and someone else checks the typing against the source. We read the records, fill the form, and put a receipt on every field that shows exactly where the value came from. A second pass flags anything that disagrees. A human signs. Nothing is invented, and nothing is retyped.

**Why a drug company cares.** A 400-patient trial produces about 290,000 data points, every one retyped from a hospital record and then checked by a monitor. That checking is 15 to 30 percent of the cost of a trial. The structured part is being automated by EHR-to-EDC vendors, but the only independent multi-sponsor study found that only about 17 percent of trial data points can be transferred that way. The rest is in scanned outside-lab reports, discharge summaries, clinic notes, and medication lists written as prose. That is the part we read.

**Why everyone else cares.** The same engine fills the New Jersey Universal Child Health Record, the form every parent in this state hands to a school each year, from a child's scattered records.

## The problem, with numbers

| Fact | Number | Source |
|---|---|---|
| Visit to data entry lag | 8 days average | Tufts CSDD 2017 eClinical Landscape |
| Monitoring and source verification share of trial cost | 15 to 30 percent | PMC4386950 |
| Error rate with 100 percent source verification vs partial | 0.27 vs 0.53 percent | PMC4386950 |
| Trial data points transferable from EHR automatically (independent study, 3 hospitals, 3 sponsors) | about 17 percent of all points; medications 7.7 percent | TransFAIR, PMC10277109 |
| Data entry per visit with a commercial EHR-to-EDC connector | 5.5 min to 2.5 min, about 70 percent of fields auto-filled | Mount Sinai, 2026 |
| Regulatory requirement | every source data point attributable, with an audit trail FDA may inspect | FDA eSource guidance 2013; FDA EHR guidance 2018 |

## The idea

Two ends and a standard middle.

- **Storing end.** Anything comes in: a FHIR record from the hospital, a PDF from a central lab, a faxed note from another clinic, a scanned worksheet. Each fact is extracted once and stored as a FHIR-shaped fact with a receipt: which document, which page, which span, or which FHIR resource; when it was true; who or what extracted it; confidence.
- **The ledger.** The append-only store of those facts. One per institution for trials. One per patient for the consumer case. Time-series and vectors on Tiger Data.
- **Retrieving end.** A form is a list of questions. The filler turns each field into a query against the ledger with a rule for recency and units, and answers it with a receipt, a confidence, or "needs a human."
- **Verifier.** An independent second pass re-derives every field and applies rules: units, visit window, plausibility, conflicts between sources. Agree, disagree, or unknown.
- **Review.** The coordinator sees only disagreements and blanks, confirms field by field, signs. The confirmed form exports to the trial database. Every action lands in an audit trail.

We do not invent a standard. FHIR is the format, USCDI the content, FHIR Provenance the receipt. We fill the standard with the data that never made it in, and we fill forms from it.

## How it runs, end to end

1. A document or record arrives and is stored unchanged with a hash.
2. The reader extracts facts with verbatim quotes and locates each quote in the source.
3. Each fact is coded to a standard concept and written to the ledger with its receipt.
4. A form definition says which facts a visit needs.
5. The filler answers each field from the ledger, newest valid value first, and attaches the receipt.
6. The verifier re-derives each field independently and compares.
7. Disagreements and blanks go to the review queue.
8. The coordinator confirms, edits, or asks the source for more, and signs.
9. The confirmed form exports to the trial database.
10. When a new document arrives later, affected forms are flagged for re-check.

## The demo, three beats

1. **Two clinics, one patient.** One clinic speaks FHIR. The other sends faxes. Both land in one ledger. The trial visit form fills itself. Click any field and the source page opens with the quote highlighted.
2. **The check.** A planted conflict: the fax says 72 kg, the EHR says 92 kg. The verifier flags it, the coordinator resolves it with one click, and the audit trail records both values.
3. **The same ledger, a different form.** The school health form for the same patient fills in seconds. Same receipts.

## Data

- Synthea: synthetic patients with labs, vitals, medications, diagnoses, exported as FHIR. The EHR.
- CDISC SDTM pilot: what a real trial collects, already loaded in our store.
- CDASH: form definitions for demographics, vitals, labs, medications, adverse events, medical history.
- Synthetic outside documents: lab PDFs, discharge summaries, clinic notes, faxes rendered as scans, generated from the same facts with planted gaps and conflicts. The answer key.
- New Jersey Universal Child Health Record (CH-14), public.

No real patient data anywhere.

## What we measure

- Percent of fields filled automatically.
- Field accuracy against the answer key.
- Verifier catch rate on planted conflicts and false alarms.
- Time per form against the 5.5 minute manual baseline.
- Receipt coverage: percent of filled fields with a located source.

## Why Tiger Data

- The ledger is a time series of observations per patient. Hypertable.
- Visit-to-entry lag per site, the Tufts metric, is a continuous aggregate.
- "Where is the most recent HbA1c in this patient's 40 documents" is a vector query.
- A trial's 290,000 points and their documents fit on the free tier with compression.

## What we keep from the current build

Model seam (Anthropic or OpenAI), evidence quotes located to offsets, the field-by-field verify-and-sign screen, append-only audit, the Tiger store with subjects, labs, vitals, events, the loaders, the form builder, the tests. Roughly half the code.

## What is new

| Component | What it is |
|---|---|
| Document store and ledger schema | Raw files, facts with receipts, FHIR-shaped |
| Reader | Documents and FHIR in, facts with located quotes out |
| Form definitions | CDASH visit pages and the CH-14 form as field lists with rules |
| Filler | Field to ledger query with recency and unit rules |
| Verifier | Independent re-derivation plus rules, per-field verdict |
| Review UI | Patient, documents, forms, disagreements, sign, export |
| Document generator | Synthetic outside documents with planted conflicts and an answer key |
| Evaluation | The five metrics above |

## What we do not claim

- Not a new interoperability standard. We use FHIR.
- Not a replacement for EHR-to-EDC connectors. We cover the data they cannot reach.
- Not clinical judgment. Causality, eligibility, and consent stay with people.
- Not free access. A form pulls only the fields it asks for, for the patient it names, under the purpose and authorization shown on screen.

## Sources

- Tufts CSDD, 2017 eClinical Landscape Study
- Monitoring and source verification cost and error rates: https://pmc.ncbi.nlm.nih.gov/articles/PMC4386950/
- TransFAIR study of EHR2EDC: https://pmc.ncbi.nlm.nih.gov/articles/PMC10277109/
- Mount Sinai EHR-to-EDC results, 2026: https://www.mountsinai.org/about/newsroom/2026/mount-sinai-tisch-cancer-center-cuts-clinical-trial-data-entry-time-by-more-than-half-with-real-time-ehr-to-edc-tech
- FDA, Electronic Source Data in Clinical Investigations, 2013
- FDA, Use of Electronic Health Record Data in Clinical Investigations, 2018
- New Jersey Universal Child Health Record: https://www.nj.gov/health/forms/ch-14.pdf
