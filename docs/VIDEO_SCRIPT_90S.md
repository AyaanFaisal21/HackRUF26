# Sourced, ninety-second script

A screen recording of the website only, no live uploads, with the narration on what happens under the hood. About 240 words, 1:30 at a normal pace. Tabs to open first: the landing page, Olu Murphy's patient page (01-701-1415), the document DOC-0041, Noah Adeyemi's Vital Signs form (Review queue, 01-704-1260, visit 2026-08-22, form 755 at the time of writing), and Metrics.

---

**[0:00, landing page, hero, one scroll to "The problem"]**

Every trial visit is typed by hand from the hospital record into the sponsor's forms, then checked by a monitor. Connectors reach seventeen percent of the data; the rest is paper. Sourced is clinical data that manages itself, with receipts.

**[0:14, Olu Murphy's patient page: "Known at", then click the weight concept]**

Under the hood, two readers feed one ledger. The hospital's FHIR bundle is mapped by rules: each observation's LOINC code becomes a concept, units converted, the original kept.

**[0:26, Documents, open DOC-0041, click a fact so its quote lights up]**

Paper goes to gpt-4.1 under a strict JSON schema: it must return every fact with a verbatim quote. A locator finds the quote on the page and stores the span. That span is the receipt. Every fact lands in a Tiger Data hypertable, partitioned by observation date.

**[0:44, Noah Adeyemi's Vital Signs form, click the flagged weight, read the likely cause]**

A form is a list of questions. The filler answers each from the ledger, nearest value to the visit inside a window. The verifier then checks the range, re-parses the quote, and compares sources measured within three days. This weight disagrees. The rules look at the patient's own history, five readings around forty-eight kilos, and propose keeping the hospital's value.

**[1:08, click "apply suggestion", type a name, sign, open the export, scroll to the history]**

One click records the decision with its reason. Signing is blocked until every flag is decided; the export is ODM-shaped, and each action is hashed into the one before it, so the audit trail is tamper-evident.

**[1:20, Metrics, the forms table, then hold on the landing page]**

All of it is scored against a planted answer key: every field filled and accurate, thirty-five of thirty-five conflicts caught, no false alarms. The model reads; the rules fill and check; the human signs.

---

Numbers and sources are in `VIDEO_SCRIPT.md`. If form 755 has been decided before you record, use any Vital Signs form in the queue whose weight shows "disagree" with a "Suggested decision" line.
