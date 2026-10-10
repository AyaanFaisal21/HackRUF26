# Decisions

## Why Day Zero

Fifty-two sheets were read. Three were spiked far enough to find their roadblocks (see `spikes/`). Day Zero won on floor, not ceiling:

- It is the only candidate whose ground truth is hundreds of real structured records (openFDA) rather than a handful of hand-made documents.
- The core is rules, not model output. Validity, seriousness, day zero, and deadlines are written in the regulations and are testable.
- There is no hard input modality. No PDF table extraction, no audio, no real-time.
- The queue with live countdowns reads as an operational tool, not an extraction demo.

Runner-up was Hidden in the Labs (sheet 08), which ran fully offline in the spike and found a genuine Hy's Law candidate in unmodified CDISC pilot data. Protocol Pre-Flight (sheet 01) parsed Lilly schedules but broke on Janssen's wrapped table headers.

## Sponsor fit

- **Tiger Data**: genuine. Intake and audit are time series (hypertables, compression, continuous aggregate). Cases are relational. Duplicate detection is a vector search. See the table in `README.md`.
- **Presage**: no. Camera vitals and emotion sensing have no place in a safety-intake workflow. Forcing it would read as padding.
- **Gemini track**: no. It targets student tools.

## Scope cuts (deliberate)

- No real MedDRA. Mock dictionary from observed terms.
- Reference safety information is synthetic. A follow-up could pull the openFDA label API.
- E2B(R3) XML export is not built. The case JSON already carries the E2B-shaped fields.
- Fax PDFs are rendered as OCR-like text, not real PDFs through Tesseract.
- Spanish and French messages need the Claude renderer (the offline generator is English only).

## Open risks

- The two LLM steps (extraction, natural-language rendering) were written against the documented SDK but not executed here because no API key was available. First task at the event: run `make load` with `DAYZERO_EXTRACTOR=claude` on ten messages.
- The hash embedder is deliberately simple. Thresholds in `dedupe.py` were tuned on oracle output and will need re-tuning on real extraction output.
