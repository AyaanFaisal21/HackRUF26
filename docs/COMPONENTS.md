# Components and work breakdown

Status at the pivot commit. Everything marked done runs from a clean clone with no model key.

## Data flow

```
CDISC pilot ──> generate.py ──> FHIR bundles (EHR)  +  documents (outside clinics)  +  answer key
                                      │                        │
                              read_fhir_bundle           ModelDocReader | OracleDocReader
                                      └──────────┬─────────────┘
                                           facts with receipts  ──> Tiger: facts hypertable, document chunks (pgvector), audit
                                                  │
                                 forms.py fill  ──> verifier.py  ──> review queue (api.py, frontend)
                                                  │
                                           sign ──> ODM-shaped export         evaluate.py ──> docs/eval-*.md
```

## Contracts

Change these only in `backend/sourced/schema.py` and tell the team.

| Contract | Signature |
|---|---|
| Document reader | `read(Document) -> DocExtraction` (facts with verbatim quotes) |
| FHIR reader | `read_fhir_bundle(bundle, patient_id, source_org) -> list[Fact]` |
| Ledger read | `store.facts(patient_id, concept, start, end) -> list[dict]` |
| Filler | `fill(store, patient_id, FormDef, visit_date) -> FormInstance` |
| Verifier | `verify(FormInstance, FormDef, llm=None) -> FormInstance` |
| API | `GET /api/patients, /api/patients/{id}, /api/patients/{id}/facts, /api/documents, /api/documents/{id}, /api/search, /api/forms, /api/queue, /api/metrics, /api/stats`; `POST /api/documents, /api/patients/{id}/forms, /api/forms/instances/{id}/fields/{key}, /api/forms/instances/{id}/sign` |

## Components

| ID | Component | Files | Status | Hours left |
|---|---|---|---|---|
| S1 | Two-clinic world and answer key | `generate.py`, `scripts/convert_cdisc.py` | done: 264 patients, 220 documents, planted gaps, unit traps, conflicts | 3 to 5 |
| S2 | Readers | `reader.py`, `llm.py` | FHIR done; model reader run on all 208 documents with gpt-4.1 (100% recall, 99.2% precision, reads cached); regex baseline for comparison; oracle done | 2 to 4 |
| S3 | Vocabulary and units | `concepts.py` | done for 20 concepts | 2 to 3 |
| S4 | Ledger on Tiger | `sql/sourced.sql`, `store.py` | done: hypertables, compression, continuous aggregate, pgvector, COPY loads | 2 to 4 |
| S5 | Forms and filler | `forms.py` | done: 6 CDASH pages and the NJ CH-14 | 3 to 5 |
| S6 | Verifier | `verifier.py` | done: 35 of 35 planted conflicts, 0 false alarms on model-read data; dose and status normalization for medication rows; model second opinion still untested | 2 to 3 |
| S7 | Review, sign, export, audit | `api.py`, `store.py` | done | 2 to 3 |
| S8 | Frontend | `frontend/src` | done: patients, patient, form review, queue, documents with search and ingest, document viewer, metrics | 6 to 10 |
| S9 | Evaluation | `evaluate.py` | done on model-read data: forms 100 percent, 35/35 conflicts, 12/12 unit traps, 32/32 gaps, 0 false alarms, 10/10 school forms; reader table versus scripts baseline by document kind and layout | 1 to 2 |
| S10 | Packaging and demo | `README.md`, `docs/`, video, slides | README with results, `docs/VIDEO_SCRIPT.md` written; recording and slides not started | 4 to 6 |

### What remains, by component

- S1: real fax images and scanned PDFs (render the generated text to PDF, add skew and noise) so the model reader is tested on images, not clean text. Spanish documents. Concomitant medication dates in prose.
- S2: image input for scanned faxes (render the generated text to PDF, add skew and noise) and re-run the reader on images; a second model for comparison.
- S3: extend the vocabulary as the model reader meets new labels; log uncoded labels from `extraction_to_facts`.
- S4: Tiger Cloud switch-over (`make check-db`, `make db-init`, `make load`), `make compress` for the size slide, index tuning if the queue slows.
- S5: visit-aware adverse event windows (previous visit date instead of 35 days); CH-14 immunization schedule completeness (which doses are due).
- S6: model second opinion on real reads; plausibility of change over time (a child gaining 6 kg in a week).
- S7: PDF export of a signed form; bulk sign; role names.
- S8: keyboard flow for review (accept, next); document viewer page thumbnails; mobile check.
- S9: a brittleness curve (recall against number of unseen layouts) if a chart is wanted for the deck.
- S10: three-minute video, 10 to 12 slides, JEDI team link.

## Critical path

1. Record the video from the script and build the slides from the README results table.
2. S8 polish and S10 video can run entirely on oracle data in parallel.
3. S4 cloud switch-over is a 15-minute task; do it early so the demo does not depend on Docker.

## Suggested split

Four people: (A) S2 and S6 with the key. (B) S1 scans and S10 video and slides. (C) S4, S7, S9. (D) S8.
Three people: (A) S2, S6, S9. (B) S1, S4, S7. (C) S8, S10.
Two people: backend owner S1 to S7 and S9 in the order S2, S4, S1, S6; frontend owner S8 and S10.

## Three-minute demo

1. 0:00 A coordinator with a 12-page visit form and a stack of faxes. A parent with a school health form and three patient portals. "Someone retypes it, someone else checks it."
2. 0:25 Patient page: two clinics, one ledger. Click "fill and verify". The vital signs page fills in milliseconds, every field with a source.
3. 0:55 Click a field. The receipt opens the fax at the page with the quote highlighted. The weight was written in pounds and converted.
4. 1:20 The verifier caught one: the note says 112 kg, the hospital says 92 kg. Both shown. The coordinator picks, writes a reason, signs. The export and the audit trail appear.
5. 2:00 The same ledger, the school form: immunizations unioned across two clinics, the urgent-care weight flagged.
6. 2:30 Metrics slide, then Tiger slide: one hypertable of 30,000 facts, compression, vector search across every page.
