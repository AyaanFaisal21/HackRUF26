# Sourced, page by page

For the team. One line per thing. Run it with `make api` and `make web`, then open http://localhost:5173.

## The agent in one breath

- **Role.** A site data agent, the "Source-to-EDC" kind in Regeneron's outline: it moves and checks clinical data.
- **What it does on its own.** Reads paper into facts with quotes. Picks the value that answers each form field. Re-derives and cross-checks every field. Names the likely cause of a disagreement and drafts a decision. Routes only the flagged fields to a person. Exports with provenance. Logs every action.
- **What it never does.** Invent a value, or sign.
- **Tangible impact, measured on our test trial.** 99.7 percent of fields filled against 68 percent reachable by structured connectors. 35 of 35 planted conflicts caught, 0 false alarms. A photographed fax becomes ten located facts in eight seconds. Every value has a receipt.
- **Why that matters.** Checking the typing is 15 to 30 percent of a trial's cost. Regeneron's own model puts an agent like this at about 40 percent fewer queries and database lock up to a month sooner.

## Home `/`

- **On the page.** The pitch, three demo buttons, live ledger counts, the problem in three numbers, how it works, what happens when two sources disagree, who uses it, a live chart.
- **Where it comes from.** Counts from `/api/stats` on Tiger Cloud. The chart from the `facts_daily` continuous aggregate. The buttons pick a documented patient, a flagged form, and a child from the API.
- **Why it is there.** The 30-second version of the story for a judge.

## Patients `/patients`

- **On the page.** All 264 patients: 254 adults from the CDISC pilot study, 10 children. Search, filter by adult or child, document and form counts.
- **Where it comes from.** The `patients` table, loaded by `make load`.
- **Why it is there.** The door into any ledger.

## Patient `/patients/:id`

- **On the page.** Identity across organizations (the hospital's number and the clinic's number). "Fill a form" with a form and a visit date. "Known at": which organizations know this person and since when. Documents received. Forms filled. "What the ledger knows": every concept with its sources and latest value; click one to see each value with its receipt.
- **Where it comes from.** The hospital's FHIR bundle, read by rules. The outside documents, read by the model with verbatim quotes.
- **Why it is there.** This is the union: one ledger per patient, every pipe joined.

## Form review `/forms/:id`

- **On the page.** The form, the patient, the visit. A verdict strip. One row per field: value, confidence, verdict, source. Click a field for the receipt panel: the receipt, why it is flagged, the likely cause with evidence, a suggested decision, the model's reading on request, the checks, the other values in the window. Decide: accept, choose another source, enter manually, leave blank, each with a reason. "Accept all unflagged". Sign and export. History.
- **List pages (medications, immunizations).** One row per drug or vaccine with every source. Conflicting rows are red and expand to show each source's page, quote, dose, and dates, plus the likely cause.
- **Where it comes from.** The filler picks the value nearest the visit at fill time. The verifier runs its rules at the same moment. Decisions come from the person. The model suggestion is a button.
- **Why it is there.** The only place a human touches the data. "People stay in the loop" happens here.

## Review queue `/queue`

- **On the page.** Every filled form, disagreements first: filled, flagged, to resolve, status, fill time.
- **Where it comes from.** The `form_instances` table.
- **Why it is there.** The coordinator's worklist. A form leaves it when it is signed.

## Documents `/documents`

- **On the page.** Vector search over every page. Ingest: paste text, or upload a photo, scan, or PDF; let the reader name the kind. The list of everything received with status, fact count, and which reader read it.
- **Where it comes from.** 208 generated documents from `make load`, plus live uploads. Search uses pgvector embeddings of each page.
- **Why it is there.** The intake end of the pipe. A fax server or an EHR export would post here.

## Document `/documents/:id`

- **On the page.** The original image if there is one. The text or transcription with every receipt highlighted. The facts table; click a fact and its words light up.
- **Where it comes from.** The model must quote every value; the locator finds the quote on the page.
- **Why it is there.** Proof that nothing was invented. Source verification becomes a click.

## Metrics `/metrics`

- **On the page.** Ledger stats. Form metrics: fill rate, accuracy, receipts, conflicts caught, unit traps, gaps filled, false alarms, school forms. Reader against the regex scripts by document kind and layout. Per concept. "Recompute live".
- **Where it comes from.** `make eval` scores the system against the planted answer key and writes `data/samples/metrics.json`.
- **Why it is there.** The "proven" gate. Evidence before an agent is allowed to act alone.

## Behind every page

- **Pipeline.** Reader (the only model) to ledger (Tiger Data) to filler (rules) to verifier (rules) to a person.
- **Data.** No real people. Trial values from the public CDISC pilot study, dates re-based. Everything else generated with a fixed seed, with planted gaps, unit traps, and conflicts in an answer key.
- **Models.** gpt-4.1 by default. Anthropic and Gemini work behind the same seam; set `LLM_PROVIDER` to switch. Cached reads mean `make load` needs no key.
- **Standards.** FHIR R4 in. LOINC codes. CDASH forms. ODM-shaped export. An audit trail shaped for FDA eSource.
