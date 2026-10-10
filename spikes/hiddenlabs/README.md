# Hidden in the Labs spike

Goal: prove the clinical rules on real CDISC pilot data and that planted signals are detectable.

## What runs
```
../../.venv/bin/python -I spike.py
```
Downloads already in `data/`: `lb.xpt`, `dm.xpt`, `ae.xpt`, `cm.xpt`, `vs.xpt`, `ex.xpt`, `ds.xpt` from the CDISC SDTM/ADaM pilot (educational-use license).

## Findings
- The pilot has 306 subjects at 17 sites, 254 randomized. Liver panel (ALT, AST, ALP, bilirubin) has an upper limit of normal on every row, so x ULN is a one-line computation.
- Hy's Law logic (ALT or AST >= 3x ULN and bilirubin >= 2x ULN, FDA DILI guidance 2009) finds exactly one natural candidate: subject 01-705-1186, bilirubin 5.9x ULN at Week 4 with a concurrent "hyperbilirubinaemia" adverse event. ALP was already 4.9x ULN at screening, so the pattern is cholestatic or pre-existing, which is exactly the nuance a medical monitor would want shown. This is a strong demo moment on unmodified real data.
- CTCAE v5 grading of post-baseline liver rows: 238 grade 1, 23 grade 2, 11 grade 3. Enough natural signal for a ranked review list without planting.
- Planted three Hy's Law subjects and one site with a slow ALT creep. Recall 3 of 3 for Hy's Law. The site creep was the top site by ALT slope with z-score 3.5 versus 0.25 for the next site.
- Blinding: the treatment arm is written to `data/UNBLINDED_arm_lookup.csv` and never joined. The eDISH plot in `data/edish.png` is blinded.

## Roadblocks found
- The three planted subjects use identical multipliers, so they overlap on the eDISH plot. Randomize the multipliers.
- The pilot data has only three serious adverse events, so the "AE to lab linking" feature needs planted AEs too.
- Patient timelines need concomitant medications (`cm.xpt`) joined by study day. Not done yet, straightforward.
- The eligibility-question assistant in the Best tier needs a protocol text and an LLM. Not needed for Better.

## Next build steps
1. Patient profile view: labs, AEs, meds on one timeline per subject.
2. eDISH with click-through to the subject profile.
3. Ranked review list with the rule and the evidence rows for every flag (already in `data/flags.json`).
