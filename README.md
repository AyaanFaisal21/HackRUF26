# Day Zero

A safety-intake agent for pharmacovigilance. It reads messy adverse-event reports, decides whether each one is a valid case, extracts the facts with evidence, starts the regulatory clock, catches duplicates, and hands a ready-to-review case to a human.

**The model extracts. The rules decide. The human confirms.**

Built for the Regeneron track at HackRU Fall 2026 (starter sheet 07, "Day Zero"). Runs on Tiger Data.

## The problem in one breath

Drug companies must collect, assess, and report possible side effects. Reports arrive as emails, faxes, call-center notes, and patient messages, in several languages. A report becomes a valid case when four facts are known: an identifiable patient, an identifiable reporter, a suspect drug, and an adverse event (ICH E2D). The day all four are known is day zero. A serious, unexpected reaction must reach FDA within 15 calendar days, or 7 if it is fatal or life-threatening (21 CFR 312.32). Case processing can consume two thirds of a safety department's resources (Schmider et al., 2019).

## What it does

Two front doors, one safety picture. Written reports (emails, call notes, portal messages, faxes, site reports) become cases with a regulatory clock. Structured trial data (daily symptom diaries, lab results, recorded events) builds a profile per patient that rules watch continuously. Both end in a physician's hands with the evidence attached, and anything serious, unexpected, and possibly related becomes a pre-filled expedited report that a provider verifies field by field before it goes anywhere.

| Step | Module | How |
|---|---|---|
| Intake | `backend/dayzero/schema.py` | One `Message` type for every channel |
| Extraction | `extract.py` | Claude structured outputs. Every field carries a verbatim quote, located to a character offset |
| Coding | `coding.py` | Mock MedDRA (terms observed in openFDA) with synonyms, fuzzy matched |
| Rules | `rules.py` | Validity (ICH E2D), seriousness (ICH E2A), expectedness against reference safety information, day zero across follow-ups, 7 or 15 day deadline (21 CFR 312.32). Each result cites its rule |
| Duplicates | `dedupe.py`, `embed.py` | Structured field agreement plus pgvector cosine similarity. Both halves are shown. A human merges |
| Follow-ups | `rules.py` | Drafted questions for each missing fact |
| Storage | `sql/schema.sql`, `db.py` | Tiger Data: hypertables for intake and audit trail, continuous aggregate for the volume chart, compression, pgvector index |
| Review | `api.py`, `frontend/` | Queue sorted by deadline, case view with highlighted evidence, merge decisions, full history |
| Evaluation | `evaluate.py` | Field accuracy, validity and day-zero accuracy, duplicate recall, against the answer key |
| Patient profiles | `trials.py`, `db_trials.py` | CDISC pilot subjects, labs, events; synthetic daily symptom diaries with planted patterns; flags with a readable logic chain (Hy's Law, CTCAE grades, persistent or jumping symptoms, site drift) |
| Physician brief | `brief.py` | Timeline, lab peaks, symptom burden, cohort context, arguments for and against relatedness, regulatory consequence. Never a conclusion. Optional model-written narrative restricted to the assembled facts |
| Expedited report | `forms.py` | Pre-filled, modelled on the sections of FDA Form 3500A, every field with its source. Provider verifies field by field, signs, then a mocked submission |
| Model seam | `llm.py` | One interface for structured and free-text calls; Anthropic or OpenAI, whichever key is present; deterministic mode with none |

## Quickstart

Requirements: Python 3.11+, Node 18+, Docker (or a Tiger Cloud service).

```bash
make setup                 # venv + pip + npm
cp .env.example .env       # add ANTHROPIC_API_KEY for live extraction; leave DAYZERO_EXTRACTOR=oracle for the offline demo
make db-up                 # local TimescaleDB with pgvector on :5433 (or set DATABASE_URL to Tiger Cloud)
make db-init               # hypertables, continuous aggregate, vector index
make load                  # run the intake pipeline over data/samples/inbox.json and load the database
make load-trial            # load the CDISC pilot trial, generate daily symptom diaries, compute flags
make api                   # http://localhost:8000/docs
make web                   # http://localhost:5173
```

Regenerate the data from scratch:

```bash
make fetch                 # 300 serious FAERS reports from openFDA, no key needed
make mock-data             # mock MedDRA list and mock reference safety information
make inbox                 # synthetic messy inbox + answer key
make eval                  # metrics against the answer key
make test
```

Live extraction with a model: put `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` in `.env`, set `DAYZERO_EXTRACTOR=model`, then `make load` and `make eval`. With no key the whole app still runs in deterministic mode (oracle extraction from the answer key, briefs without a narrative paragraph).

## Data

- **Ground truth**: openFDA `drug/event` records (FAERS), structured in the E2B format. See `data/README.md`.
- **Messy inbox**: generated from those records. FAERS has no names, narratives, or contact details, so the generator invents them and keeps them as the answer key. Some reports are made invalid on purpose, some are duplicated by a second reporter, some get follow-ups.
- **Dictionary**: MedDRA is licensed. `data/mock_meddra.json` is the set of preferred terms observed in the sample.
- **Reference safety information**: `data/mock_rsi.json` is synthetic and says so in the file.

FAERS reports are not proof that a drug caused an event. No real patient identifiers are used anywhere.

## Why Tiger Data

| Need | Tiger feature | Where |
|---|---|---|
| Intake is a time series with spikes, aging, and retention | Hypertable on `messages(received_at)` | `schema.sql` |
| Audit trail that is append-only and queryable by time | Hypertable on `case_audit(at)` | `schema.sql`, `db.audit` |
| Live intake chart without a reporting job | Continuous aggregate `intake_hourly` | `db.intake_series` |
| Millions of reports on a free tier | Compression policy on `messages` | `db.stats` |
| Patient, drug, reporter, case relationships | Plain SQL tables and the `queue` view | `schema.sql` |
| Semantic duplicate detection | pgvector `vector(384)` with HNSW cosine index | `db.candidates` |
| 216,000 daily symptom rows per trial, growing every day | Hypertable `diary_entries` with compression after 60 days | `trial_schema.sql` |
| Weekly symptom burden chart on the signal watch | Continuous aggregate `diary_weekly` | `db_trials.signals` |
| Lab results over time per patient | Hypertable `lab_results` | `trial_schema.sql` |

## Rules of the road

Synthetic or public de-identified data only. A human reviews every case before anything is submitted. Nothing here is medical or legal advice. Vendor names are examples, not endorsements.

## Sources

- ICH E2D(R1), Post-approval safety data management, minimum criteria for a valid report
- ICH E2A, Clinical safety data management, definitions of serious
- 21 CFR 312.32, IND safety reporting, 7 and 15 day timelines
- ICH E2B(R3), electronic transmission of ICSRs
- Schmider J. et al., 2019, Innovation in pharmacovigilance: use of artificial intelligence in adverse event case processing
- openFDA drug adverse event API, https://open.fda.gov/apis/drug/event/

## License

MIT. See `LICENSE`.
