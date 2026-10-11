# Sourced, video script (3:00 limit)

A screen recording of the website, start to finish, with one switch to the Tiger Cloud tab. No slides. The landing page carries the hook and the problem; the other pages carry the technical depth; the upload is live. Narration is about 440 words, 2:45 at 160 words a minute. Every number is in the table at the end with its source.

---

**[0:00, website, landing page, hero in view]**

One Phase 3 trial. Four hundred patients, twelve visits, sixty fields a visit. Two hundred ninety thousand data points, each typed by hand from the hospital record into the sponsor's forms, then checked against the source by a monitor.

**[0:14, scroll to "The problem", the three numbers]**

The median pivotal trial costs nineteen million dollars; fifteen to thirty percent of that is the checking. Connectors automate the structured part: the one independent study, TransFAIR, moved seventeen percent of the data. The rest is faxes, notes, and other sites' records.

**[0:30, back up to the hero, then scroll through "How it works"]**

So we made Sourced. Clinical data that manages itself, with receipts. One ledger per patient, forms that fill from it, a verifier on every field, a person deciding only what disagreed. The unglamorous plumbing, with people in the loop.

**[0:45, Patients, then Olu Murphy's page: "Known at", the documents, click the weight concept]**

One patient, two organizations. The hospital's FHIR record is read by rules. The clinic's faxes are read by the model, which must quote every value, located to a page. One ledger, a receipt on every fact.

**[1:00, Review queue, open Noah Lee's school form, click the flagged weight]**

Disagreements first. Rules fill a form in milliseconds; more rules re-derive every field and compare sources. This weight is flagged: who said what, where, and when; the likely cause from the patient's own history; a suggested decision. The model can add a second reading, only from the receipts.

**[1:20, apply the suggestion, type a name, sign, open the export, scroll to the history with the chain badge]**

The coordinator decides, signs, exports in the trial database's format, and every action goes into a hash-chained audit trail. Regeneron's site agent outline asks for the source cited and traceable, acting alone once proven, the coordinator accountable.

**[1:36, Metrics: the forms table, then the reader table's "variant layouts" row]**

Proof before autonomy. Against a planted answer key: every field filled and accurate, thirty-five of thirty-five conflicts caught, no false alarms. The regex scripts sites use today read under one percent of an unfamiliar layout. The reader reads all of it.

**[1:51, switch to the Tiger Cloud tab: Overview with the storage panel, then Explorer with `facts` expanded]**

It lives on Tiger Data. The facts table is a hypertable chunked by time, so "nearest reading to this visit" opens one chunk. Old history compresses in place; that columnstore is it. The home chart is a continuous aggregate. Document search is pgvector in the same database. One Postgres, four shapes of data.

**[2:10, back to the website, Documents: patient id, organization, choose the photo, "store and read the photo"; then the patient page]**

Now the plumbing, live. A photo of a fax from a walk-in clinic. Eight seconds later it is ten facts, every quote located, pounds to kilograms. The patient's document list already has it.

**[2:25, fill Vital Signs for 2026-09-06; click the flagged weight]**

Fill the vital signs page. Four values agree with the hospital. One does not: the fax says one ninety pounds, the hospital says seventy-eight kilos, and the patient's own history sides with the hospital. Flagged, explained, suggested, not decided.

**[2:40, landing page, "How it works", hold]**

Sourced is the middle of the pipe. FHIR and faxes come in; signed, sourced records go out to the trial database. The model reads. The rules fill and check. The human signs.

---

## Where the time goes away

| Who | Today | With Sourced | Evidence |
|---|---|---|---|
| Study coordinator | Types every visit into the EDC from the chart, days after the visit | Picks the form and the visit; decides only flagged fields; signs | Connectors cut entry from 5.5 to 2.5 minutes a visit on structured data (Mount Sinai 2026); Sourced covers paper too |
| Monitor (CRA) | Travels to the site to compare the EDC with the source, field by field | Clicks the receipt; the source opens with the quote highlighted | Monitoring and source verification are 15 to 30 percent of trial cost (PMC4386950) |
| Data manager | Raises queries months later when values disagree | Disagreements are caught at fill time with both sources attached | Regeneron's eSource model: about 40 percent fewer queries; lock 0.5 to 1 month sooner |
| Any clinician with forms | Digs through records in several systems for a school or camp form | Same ledger, one click; immunizations unioned across clinics | 10 of 10 school forms complete across two clinics |

## Numbers in the narration

| Number | What it is | Source |
|---|---|---|
| 290,000 | 400 patients x 12 visits x 60 fields, a typical Phase 3 | arithmetic |
| $19 million | median cost of a pivotal trial | Moore et al., JAMA Internal Medicine 2018 |
| 15 to 30 percent | monitoring and source data verification share of trial cost | PMC4386950 |
| 8 days | average visit to data entry lag | Tufts CSDD 2017 eClinical landscape |
| 17 percent | data points transferred by EHR-to-EDC connectors; 16.9 percent, medications 7.7 percent, 48 percent of compared points absent from the structured record | TransFAIR, BMJ Health & Care Informatics 2023, PMC10277109 |
| 74 percent, under 1 percent | scripts baseline recall on standard layouts (74.1) and variant layouts (0.7); a third of documents are variant | `docs/eval-sourced-model.md` |
| 68 percent, 99.7 percent | visit-page fields a structured-only connector would fill, and fields Sourced fills, on the 128 demo forms | `docs/COMPONENTS.md`, section "Coverage" |
| 8 seconds, 10 facts | `data/samples/fax_demo_upload.jpg`, transcribed and read live with gpt-4.1 (7.5 s in the dry run) | measured 2026-10-11 |
| 40 percent fewer queries, 0.5 to 1 month | Regeneron site agents outline, lock estimate | HWei outline, page 1 |

## Optional cut-ins if there is time

- "Explain with the model" on the flagged field: the model reads only the receipts and writes three sentences; the answer is stored on the field and audited.
- The review queue: disagreements first, fill time in milliseconds per form.
- Noah Lee's school form: ten immunization rows, five known only to the pediatrician and five only to urgent care.
- Olu Murphy's medication log: a drug the hospital says ended that the pharmacy fax still lists.
- Vector search on the Documents tab: find the fax that mentions a drug.

## Recording notes

- Open these before recording: the website (landing page), the Tiger Cloud console on the service Overview with the storage panel visible, and a second console tab on Explorer with the `public` schema expanded and `facts` selected so the chunks show. Hide the bookmarks bar.
- Tiger tab, if you want one query on screen: paste `SELECT hypertable_name, num_chunks, compression_enabled FROM timescaledb_information.hypertables;` into the SQL Editor beforehand and press Run while speaking. It returns facts, 24 chunks, compression on.
- Website pages in order: landing, Patients, Olu Murphy (01-701-1415), Review queue, Noah Lee's school form (top of the queue), Metrics, Documents, then the patient page again for the fill.
- **The live upload is `data/samples/fax_demo_upload.jpg`.** It is not in the ledger. On the Documents tab enter patient id `01-701-1415`, organization `Riverside Walk-in Clinic`, leave the kind on "let the reader decide" and the date empty, choose the file, click "store and read the photo, scan, or PDF". Ten facts, dated 2026-09-06 from the document. Then on the patient page fill Vital Signs for `2026-09-06`: blood pressure, pulse, and temperature agree with the hospital's visit the day before; the weight, 190 lbs, is flagged, and the likely cause says it is out of line with the patient's year of readings and suggests the hospital's 78.02 kg.
- To re-record, remove it first so the upload is fresh again (the audit events stay, the chain is append-only):

```bash
cd /Users/ayaanfaisal/Documents/HackRUF26 && PYTHONPATH=backend ./.venv/bin/python -m sourced.cli forget DOC-U30FBC36F
```

- `data/samples/fax_walkin_olu_murphy.jpg` is the first photographed fax and is already in the ledger as DOC-UABB14A3C, with its vital signs page (2026-07-06) filled. Use it to show a processed photo on the Document page; uploading it again is refused as a duplicate.
- Record at 1440 wide. The landing page and the form review page are the two screens that carry the story; linger on them.
- Two safe cuts if the take runs long: the "Every source lands in one ledger" line at 0:58, and the last sentence of the 2:03 block.
