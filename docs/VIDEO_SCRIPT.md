# Sourced, 2:30 video script

Spoken at a normal pace this is about 370 words. Screen directions are in brackets. Numbers in the narration come from `docs/eval-sourced-model.md`; update them if you regenerate.

---

**[0:00, black screen, a counter ticking up fast]**

One Phase 3 trial. Four hundred patients, twelve visits each, sixty fields a visit. That is two hundred and ninety thousand data points. Every one of them is typed by a person from a hospital record into the sponsor's forms. Then a second person flies to the site to check the typing against the source.

**[0:15, the counter stops at $19,000,000; "15 to 30 percent" fades in]**

The median pivotal trial costs nineteen million dollars, and fifteen to thirty percent of that is the checking. The tools that automate it only reach the structured part, about seventeen percent of the data. The rest is faxes, scanned lab reports, and clinic notes.

**[0:30, cut to the app, Home page]**

This is Sourced. Medical forms that fill themselves, with receipts.

**[0:35, Patient page for a documented adult; point at "Known at"]**

Here is one patient known to two clinics. The hospital sends a structured record. The outside clinic sends a two-page note and a fax. Every fact from both lands in one ledger, on Tiger Data, with where it came from.

**[0:48, click a concept in "What the ledger knows", show the weight row written in pounds]**

The note wrote the weight in pounds. The ledger has it in kilograms, and keeps what was written.

**[0:55, choose Vital Signs, pick the visit date, click "fill and verify"]**

Pick a form and a visit. The form fills in milliseconds. Every field shows its source and a verdict.

**[1:05, Form review, click the weight field flagged "disagree"]**

The verifier caught one. The hospital says ninety-two kilograms, the clinic note says one hundred twelve, measured the same day. Both receipts, side by side.

**[1:15, click the receipt link, Document viewer opens with the quote highlighted]**

Click the receipt and the fax opens on the page, with the exact words highlighted. Nothing was retyped and nothing was invented: the reader must quote every value, and the system locates the quote.

**[1:28, back on the form: accept all unflagged, decide the weight with a reason, type a name, sign]**

The coordinator decides only the fields that were flagged, writes a reason, and signs. The export is in the trial database's format, and every decision is in the audit trail.

**[1:42, Patient page for a child, fill the NJ Universal Child Health Record]**

Same ledger, different form. A New Jersey school health record: immunizations unioned across two clinics, an urgent-care weight that disagrees with the pediatrician's, flagged the same way.

**[1:55, Metrics page, the reader table]**

Measured against an answer key of sixteen hundred facts across two hundred documents: hand-written scripts recover forty-four percent of them. On layouts they were not written for, under one percent. The reader recovers one hundred percent at ninety-nine percent precision, and every quote is located. Forms fill completely, with no false alarms, and every planted conflict is caught.

**[2:12, slide: one line]**

The model reads. The rules fill and check. The human signs.

**[2:17, slide: Tiger Data]**

One database holds the ledger as a time series, the documents as vectors, and the audit trail. The ledger stays with the hospital. Only the signed form leaves.

**[2:25, end card]**

Sourced. Nobody should retype a blood pressure.

---

## Recording notes

- Use the local database for the recording so clicks are instant; Tiger Cloud adds network latency to each page.
- Before recording: `make load`, `make fill`, then open the first documented adult and confirm the weight field is flagged. Pick a patient whose note is on the variant layout so "B/P" and "Wt." are visible in the highlight.
- Counter animation for the cold open: any screen-recorder overlay, or a 3-second title card with the three numbers appearing one after another.
- The $19 million and 15 to 30 percent figures are from Moore et al. 2018 and the monitoring cost review cited in the README. The 17 percent is TransFAIR. Keep the sources slide at the end of the deck.
