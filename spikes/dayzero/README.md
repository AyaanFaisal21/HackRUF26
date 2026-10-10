# Day Zero spike

Goal: prove the deterministic core and the data path before any LLM work.

## What runs
```
../../.venv/bin/python spike.py
```
- `rules.py`: validity (ICH E2D four minimum criteria), seriousness (21 CFR 312.32(a)), day zero across a message chain, due date (7 or 15 calendar days), structured duplicate scoring. No model calls.
- `spike.py`: loads 300 serious FAERS reports from openFDA (`data/faers_*.json`), normalizes them to the ICSR schema, builds a synthetic inbox with planted invalid cases, follow-ups and duplicates, runs the rules, prints a queue and duplicate precision and recall.

## Findings
- openFDA works with no key. 300 records in three calls.
- Field availability in serious 2024 reports: sex 87%, age 59%, event date 51%, suspect drug 99%, reporter qualification 100%.
- FAERS has no patient names or initials, no reporter names, and no narrative text. The "identifiable patient" and "identifiable reporter" criteria must be synthesized. The sheet expects this, but it means the hardest extraction targets are the ones we invent, so the generator must be documented carefully.
- One quarter of records list more than five drugs. Narratives generated from those will be long. Cap suspect drugs at three per synthetic message.
- The reaction terms shipped by openFDA are MedDRA preferred terms. 527 distinct terms in 300 records. That is the mock dictionary for free.
- Rules engine: all three planted no-reporter and no-patient variants were held as not valid, and day zero moved to the follow-up date in 43 of the 200 synthetic cases (the planted ones plus the ones where FAERS itself lacked age and sex).
- Duplicate matcher on structured fields: recall 1.00 at threshold 0.6 and 0.95 at 0.7 with zero false positives among 549 random pairs. This is measured on answer-key records, not on extracted text, so the real number depends on extraction quality.

## Unproven in this environment
- The LLM extraction step. No API key was available here (api.anthropic.com returned 401). The team needs an Anthropic or Gemini key before the hackathon. Extraction must return source spans so every field links to text.
- Narrative generation (the structured-to-messy rewrite) is also an LLM step. The template narrative in `spike.py` is a placeholder.

## Next build steps
1. `extract.py`: Claude structured output -> ICSR with `source_spans`.
2. `generate.py`: FAERS case -> email, call note, portal message, fax PDF, with Spanish and French variants.
3. Queue UI with countdown and duplicate evidence panel.
