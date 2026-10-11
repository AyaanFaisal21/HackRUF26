# Sourced, video script (3:00 limit)

Narration is about 460 words, which is 2:50 at 160 words a minute. Screen directions are in brackets. Every number in the narration is in the table at the end with its source. If you regenerate the evaluation, update the numbers here and in the README together.

---

**[0:00, black screen, a counter ticking up fast]**

One Phase 3 trial. Four hundred patients, twelve visits, sixty fields a visit. Two hundred ninety thousand data points, each typed by hand from a hospital record into the sponsor's forms, then checked by a monitor against the source.

**[0:15, the counter stops; "$19,000,000", "15 to 30%", "8 days" fade in one by one]**

The median pivotal trial costs nineteen million dollars. Fifteen to thirty percent of that is the checking. The typing runs eight days behind the visit.

**[0:26, cut to the landing page, hero]**

So we made Sourced. Clinical data that manages itself, with receipts. It reads the records, structured or faxed, keeps every fact with its origin, fills the form, checks it again, and asks a person only about what disagreed.

**[0:42, Documents tab. Choose the photographed fax from the recording notes, click "store and read the photo", wait, open the document: the photo beside its transcription]**

The part no connector reaches: a photo of a fax from a walk-in clinic. Eight seconds later it is ten facts. The reader must quote every value, and each quote is located to a page and a span. Pounds became kilograms, and what was written is kept.

**[0:58, Patient page for Olu Murphy. Point at "Known at", then at the weight concept]**

Every source lands in one ledger per patient.

**[1:03, choose Vital Signs, visit date 2026-07-06, click "fill and verify"]**

Pick a form and a visit. It fills in milliseconds, every field with a receipt and a verdict. The fax weight agrees with the hospital's scale from the day before. The blood pressure does not.

**[1:17, click the flagged field. Read "Why it is flagged". Click the receipt, the fax opens highlighted. Back. Choose a value, type a reason, sign, open the export]**

Flagged, not guessed. The field says who recorded what, where, and when. The receipt opens the fax, words highlighted. The coordinator picks, gives a reason, signs. The export is in the trial database's format. Every action is in the audit trail.

**[1:35, Metrics tab, scroll to the reader table, hover the "variant layouts" row]**

You are probably wondering why this does not exist already. Connectors move structured hospital data into trial databases. The one independent study, TransFAIR, moved seventeen percent of the data. The rest was free text, paper, or another site's records. Sites patch that with scripts. Here is ours. Seventy-four percent on the layouts it was written for. Under one percent on the ones it was not. And a third of real documents are the ones it was not.

**[2:03, landing page, "How it works", one row per sentence]**

Our answer is four agents, and only one is a model. The reader turns free text into facts and must quote. The ledger unions every organization. The filler maps facts to the validated form. The verifier re-derives every field and compares sources. Each is checked by the next, so the model can be wrong and the form still cannot lie. On our test trial, structured data alone fills sixty-eight percent of the fields. With the reader, ninety-nine point seven.

**[2:30, slide: the Regeneron site agent families with "Source-to-EDC" circled; then the standards chips]**

On Regeneron's own site agent map this is the source-to-EDC data agent: acts alone once proven, study coordinator accountable. Everything it speaks, sites already run. FHIR in. LOINC codes. CDASH forms. ODM out. An audit trail built for FDA eSource. On Tiger Data.

**[2:45, landing page, "Who uses it"]**

The coordinator stops typing. The monitor verifies with a click. The data manager gets fewer queries. A pediatrician fills a school form from the same ledger. The model reads. The rules fill and check. The human signs.

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
| 8 seconds, 10 facts | the photographed walk-in clinic fax in `data/samples`, transcribed and read live with gpt-4.1 | measured 2026-10-11 |
| 40 percent fewer queries, 0.5 to 1 month | Regeneron site agents outline, lock estimate | HWei outline, page 1 |

## Optional cut-ins if there is time

- "Explain with the model" on the flagged field: the model reads only the receipts and writes three sentences; the answer is stored on the field and audited.
- The review queue: disagreements first, fill time in milliseconds per form.
- Noah Lee's school form: ten immunization rows, five known only to the pediatrician and five only to urgent care.
- Olu Murphy's medication log: a drug the hospital says ended that the pharmacy fax still lists.
- Vector search on the Documents tab: find the fax that mentions a drug.

## Recording notes

- Open these tabs before recording: landing page, Documents, Olu Murphy's patient page (01-701-1415), Metrics. Hide the browser bookmarks bar.
- The photographed fax is `data/samples/fax_walkin_olu_murphy.jpg`. On the Documents tab enter patient id `01-701-1415`, source organization `Riverside Walk-in Clinic`, leave the kind on "let the reader decide" and the date empty, choose the file, click "store and read the photo, scan, or PDF". The reader names it a clinic note dated 2026-07-06 and returns ten facts. If you prefer to paste text instead, this is the same note:

```
WALK-IN CLINIC OF HOBOKEN            FAX 201-555-0144
Progress note                        Date of visit: 07/06/2026
Patient: Olu Murphy     DOB 11/23/1940     Acct 44-2210

Vitals: B/P 128/82   P 72   T 98.4 F   Wt 172 lbs
Labs drawn today: ALT 28 U/L
Meds reviewed: Ocuvite 1 tablet BID, continue.
Plan: follow up with primary in 3 months.
```

- The hospital weighed this patient at 78.02 kg on 2026-07-05. The fax says 172 lbs, which is 78.02 kg, so the weight agrees. The blood pressure, pulse and temperature differ from the hospital's values on 2026-07-05, so they come back "disagree", each with a likely cause from the rules. Fill Vital Signs for 2026-07-06.
- The fax also says Ampicillin's course was completed in May. On the Medications page that is a second witness for the hospital's stop date against the pharmacy list, and the rules already say a dispensing list cannot show a stop.
- The document id is derived from the file or the text, so sending the same fax twice is rejected with its existing id. If you re-record, delete the document first or change one character.
- Record at 1440 wide. The landing page and the form review page are the two screens that carry the story; linger on them.
- Two safe cuts if the take runs long: the "Every source lands in one ledger" line at 0:58, and the last sentence of the 2:03 block.
