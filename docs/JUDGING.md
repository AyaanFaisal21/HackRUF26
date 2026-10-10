# Judging map

## Regeneron (from the challenge PDF)

| Criterion | Where we answer it |
|---|---|
| Utility and relevance: a real bottleneck | Case intake is the largest manual cost in drug safety. Deadlines are legal. The queue is what a case processor opens in the morning |
| Readiness: functional, replicable, deployable | `make demo` from a clean clone. MIT license. Tests. Offline mode with no keys |
| Design and packaging | 3-minute video, 10-12 slides, README with quickstart, UI that shows evidence for every field |

## Starter sheet 07 rubric

| Criterion | Where |
|---|---|
| Would a case processor meet deadlines more easily | Queue sorted by due date, live countdown, day zero computed across follow-ups |
| Runs from a clean clone | `README.md` quickstart, `Makefile` |
| openFDA ground truth plus believable synthetic narratives | `data/README.md`, `generate.py`, answer key |
| Every extracted field links back to text | Evidence quotes with character offsets, highlighted in the UI |
| Clean code, clear story, good UI | Module per concern, typed contracts in `schema.py` |

Tier reached: Better (queue, prioritization, duplicates with explanation, follow-up questions) plus Best features: follow-up merging with change history, reviewer screen, live countdown. Not built: multilingual intake, E2B export.

## Tiger Data (MLH)

| Tiger pitch | Our use |
|---|---|
| Standard SQL | Whole schema is SQL. Queue is a view |
| Unified data stack: relational plus high-frequency streams | Cases and drugs relational; messages and audit as hypertables |
| Instant dashboards with continuous aggregates | `intake_hourly` feeds the intake chart |
| 90%+ compression | Compression policy on `messages`, stats exposed at `/api/stats` |
| Vectors | pgvector HNSW index for semantic duplicate candidates |
