# Components and work breakdown

Status as of the first commit (2026-10-10). Everything marked **done** runs from a clean clone with no API key. Hours are estimates for one person during the hackathon.

## Data flow

```
openFDA FAERS ──> generate.py ──> inbox.json + answer_key.json
                                       │
                 Message ──> extract.py ──> Extraction (fields + verbatim quotes + offsets)
                                       │
                            coding.py (mock MedDRA)      embed.py (vector)
                                       │                       │
                            rules.py: merge snapshots, validity, seriousness, expectedness,
                                      day zero, 7/15 day deadline, follow-up questions
                                       │
                            pipeline.py: follow-up attach | duplicate candidates | audit
                                       │
                            db.py ──> Tiger Data (hypertables, CAGG, pgvector, compression)
                                       │
                            api.py ──> frontend/ (queue, case view, merge, history)
                                       │
                            evaluate.py ──> docs/eval-*.md
```

## Contracts between components

Change a contract only by editing `backend/dayzero/schema.py` and telling the team. Everything else is replaceable per module.

| Contract | Signature |
|---|---|
| Extractor | `extract(Message) -> Extraction` |
| Embedder | `embed(str) -> list[float]` (384 dims; the SQL column must match) |
| Coder | `code(term: str) -> (preferred_term or None, score)` |
| Rules | `assess(CaseState, rsi: dict, coder) -> Assessment` |
| Pipeline | `process(Message) -> CaseRecord` |
| Store | `save_message, candidates, cases_with_drugs, open_invalid_cases, get_case, case_for_message, save_case, save_duplicate, audit, next_case_id` |
| API | `GET /api/queue, /api/stats, /api/stats/intake, /api/cases/{id}, /api/cases/{id}/history` and `POST /api/cases/{id}/fields, /api/cases/{id}/duplicates, /api/messages` |

## Components

| ID | Component | Files | Status | Hours left |
|---|---|---|---|---|
| C1 | Data and ground truth | `generate.py`, `cli.py` (fetch, build-mock-data, build-inbox), `data/README.md` | offline generator done: 87 messages, 16 follow-ups, 11 duplicates | 4 to 6 |
| C2 | Extraction | `extract.py` | Claude path written, never executed (no key here); oracle path done | 5 to 8 |
| C3 | Rules and case engine | `rules.py`, `coding.py`, `pipeline.py` | done, 8 tests pass | 3 to 5 |
| C4 | Duplicates and vectors | `dedupe.py`, `embed.py` | done with hash embedder; recall 11/11, 14 false-positive pairs on 71 cases | 3 to 5 |
| C5 | Tiger Data layer | `sql/schema.sql`, `db.py`, `docker-compose.yml` | validated on local TimescaleDB; Tiger Cloud not yet provisioned | 2 to 4 |
| C6 | API | `api.py` | all endpoints smoke-tested | 2 to 3 |
| C7 | Frontend | `frontend/` | builds; queue, case detail with highlights, merge, history | 8 to 10 |
| C8 | Evaluation, packaging, demo | `evaluate.py`, `README.md`, `docs/`, video, slides | oracle eval done; real eval, video, slides not started | 6 to 8 |
| C9 | Patient profiles and flags | `trials.py`, `db_trials.py`, `sql/trial_schema.sql`, pages `Trials`, `Trial`, `Patient` | done: 254 subjects, daily diaries, 53 flags with logic chains, charts, confirm or dismiss | 3 to 5 |
| C10 | Physician brief | `brief.py`, `Patient.jsx` | done deterministically; narrative needs a model key; concomitant meds not loaded | 2 to 4 |
| C11 | Expedited report queue | `forms.py`, pages `FdaQueue`, `FdaForm` | done: pre-filled from cases and from signed briefs, field-by-field verification, mocked submit | 2 to 3 |
| C12 | Signal watch | `db_trials.signals`, `Signals.jsx` | done: weekly severe-symptom chart from the continuous aggregate, flags by rule, top events | 2 to 3 |

### C1 Data and ground truth

Purpose: believable messy input with an exact answer key.

Done: FAERS fetch, mock MedDRA (374 terms), mock RSI (70 products), template renderer for email, call note, patient portal, fax text, site report. Invalid variants, follow-ups, second-reporter duplicates. Receive times rebased to the last 30 days so clocks are live.

Remaining:
- `ClaudeRenderer` with the same signature as `OfflineRenderer.render`: natural wording, typos, signatures, and 15% Spanish or French. Keep the answer key identical.
- Harder planted cases: relative dates ("last Tuesday"), two patients in one email, dose with units, a reporter who is also the patient.
- Raise the sample to 200 messages. Keep `--seed 7` so numbers are reproducible.
- Optional: render the fax channel as a real PDF and OCR it (pypdf or Tesseract).

Done when: `make inbox` writes 200+ messages including non-English ones, every answer-key quote locates in its body, `data/README.md` describes every variant.

### C2 Extraction

Purpose: the only model call in the system. Everything downstream is already tested against the oracle.

Remaining:
- Run `DAYZERO_EXTRACTOR=claude` on 10 messages. Check `stop_reason`, quote-locate rate, and field accuracy. Iterate the system prompt in `extract.py`.
- Concurrency (thread pool of 4) and the SDK's built-in retries. Log `response.usage` per message for the cost slide.
- Decide the bulk model. Default is `claude-opus-5-5`; `claude-sonnet-5-5` is the cheaper option for 200 messages. Keep `DAYZERO_MODEL` as the switch.
- Optional: Message Batches for the full inbox at half cost.

Done when: `DAYZERO_EXTRACTOR=claude make eval` prints a field-accuracy table and quote-locate rate is at least 95%.

Risk: this is the critical path. Get an API key before anything else.

### C3 Rules and case engine

Purpose: the defensible core. Every output cites its regulation.

Remaining:
- Real reference safety information: pull `openfda.brand_name` labels from the openFDA label API, extract the adverse reactions section, match coded terms. Replace `mock_rsi.json` behind the same dict shape.
- E2B(R3)-style export endpoint (JSON first, XML if time). The case record already carries the E2B-shaped fields.
- Unit tests for `followup_score` and for merge with change history.
- Coder synonyms: extend the lay-language map from the terms the generator uses.

Done when: an exported case opens in a JSON viewer with every E2B section populated, and tests cover the follow-up scorer.

### C4 Duplicates and vectors

Purpose: surface candidates with evidence; the human merges.

Remaining:
- Real embeddings. Preferred: Tiger's pgai vectorizer so embeddings are generated in the database. Fallback: a hosted embedding model called from `embed.py`. Update `vector(384)` in `schema.sql` to the new dimension.
- Retune `WEIGHTS`, `LIKELY`, `POSSIBLE` in `dedupe.py` using the false-positive count from `make eval`.
- Show the per-field evidence in the UI (API already returns it).

Done when: recall stays at 11/11 and false-positive pairs drop below 5 on seed 7.

### C5 Tiger Data layer

Purpose: the sponsor prize and the operational backbone.

Done: `messages` and `case_audit` hypertables, compression policy, `intake_hourly` continuous aggregate with refresh policy, pgvector HNSW index, `queue` view, `PgStore`.

Remaining:
- Provision a Tiger Cloud service, run `make db-init` against it, set `DATABASE_URL`.
- Make compression visible for the demo: call `compress_chunk` on old chunks or shorten the policy interval, then show `/api/stats`.
- Index `cases(due_date)` and `messages(case_id)`.
- Optional: a second continuous aggregate for cases created per day by seriousness.

Done when: the app runs against the Tiger Cloud URL and `/api/stats` reports compressed chunks greater than zero.

### C6 API

Remaining:
- CORS middleware for a deployed frontend.
- `POST /api/messages` live-ingest demo with the Claude extractor (today it needs the oracle answer key).
- `PATCH /api/cases/{id}` to close a case, with audit.
- Export endpoint from C3.

Done when: the live demo can paste one new email and get an assessed case back in the queue.

### C7 Frontend

Done: queue sorted by deadline with days-left pills, case detail with highlighted evidence, duplicate decisions, history.

Remaining:
- Intake chart from `/api/stats/intake` (the continuous aggregate). Plain SVG or Recharts.
- Day-zero timeline strip per case: first message, follow-up, day zero, due date, today.
- Countdown in hours when under two days.
- Field confirm and edit controls calling `POST /api/cases/{id}/fields`.
- Filters: overdue, serious, not valid, has duplicates.
- "Process inbox" button for the video: posts the sample messages one by one and watches the queue fill.
- Visual polish for the recording.

Done when: a judge can follow the three-minute script below without the presenter touching the terminal.

### C8 Evaluation, packaging, demo

Done: `evaluate.py`, `docs/eval-oracle.md`, README, MIT license, decisions log, judging map.

Remaining:
- Real extraction numbers from C2, with a short failure analysis (which fields miss and why).
- Final README pass: screenshots, exact clean-clone steps verified by someone who did not write them.
- 3-minute video (script below). 10 to 12 slides.
- Submission: GitHub link, video link, the JEDI team link for every member.

Done when: a teammate who was not involved clones the repo on a fresh laptop and reaches the queue in under ten minutes.

### C9 to C12, what remains

- C9: load concomitant medications (`cm.xpt`) into the profile and the brief; tune the diary jump rule against `data/samples/trial_answer_key.json`; a flag evaluation table (planted versus found) for the deck.
- C10: run the narrative with a real key and check it adds no facts; add "similar cases in public data" from openFDA by vector search.
- C11: E2B(R3)-shaped JSON export next to the form; a real 3500A field map if a judge asks.
- C12: alert when a term's weekly count exceeds its trailing baseline; click-through from a bar to the subjects behind it.

## Dependencies and critical path

- C2 blocks the real numbers in C8 and the live demo in C6. Start it in hour one.
- C5 cloud provisioning blocks nothing technically but takes elapsed time (signup, service creation). Start it in hour one in parallel.
- C7 is the longest single stream. It can proceed entirely on the offline data.
- C1 improvements feed C2 testing, so land the Claude renderer early, then widen the data.

## Suggested split

Four people: (A) C2 then C3. (B) C1 then C8 video and slides. (C) C4, C5, C6. (D) C7.

Three people: (A) C2, C3, C8 numbers. (B) C1, C4, C5, C6. (C) C7, C8 video.

Two people: backend owner takes C1 to C6 in the order C2, C5, C4, C1, C3, C6. Frontend owner takes C7 and C8.

## Timeline for a 24-hour build

| Hours | Goal |
|---|---|
| 0 to 2 | Keys in `.env`, `make demo` works for everyone, Tiger Cloud signup started, Claude extraction on 10 messages |
| 2 to 8 | Good tier on real extraction: inbox in, queue out, evidence highlights. First eval table |
| 8 to 16 | Better tier: duplicates UI, follow-up timeline, intake chart, Tiger Cloud switch-over, real RSI |
| 16 to 20 | Retune duplicates, failure analysis, README verified from a clean clone |
| 20 to 24 | Code freeze. Video, slides, submission |

## Three-minute demo script

1. 0:00 The clock. "A report arrives. The moment the fourth fact is known, a legal countdown starts: 15 days, or 7 if someone died."
2. 0:30 Inbox of five messages: an email, a call note, a portal message in Spanish, a fax, a follow-up. Press process. Queue fills with countdowns.
3. 1:10 Click the fatal case. Every field highlighted in the source text. Seven-day clock, with the regulation cited.
4. 1:40 Click the case missing a reporter. "Not yet valid." Drafted follow-up question. The follow-up arrives. Day zero moves. History shows both states.
5. 2:15 Click the duplicate. Field-by-field evidence and vector similarity. Merge. Audit trail.
6. 2:40 Numbers slide: field accuracy, validity accuracy, duplicate recall. Tiger slide: hypertables, continuous aggregate, compression, pgvector, one database.
