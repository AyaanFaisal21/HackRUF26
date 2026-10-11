## Evaluation (reader: oracle)

Patients scored: 60. Fields with a known truth: 1089.

| Metric | Value |
|---|---|
| Fields filled automatically | 100.0% |
| Accuracy of filled fields | 100.0% |
| Filled fields with a receipt | 100.0% |
| Planted conflicts caught by the verifier | 8/8 |
| Unit traps converted correctly | 15/15 |
| Gaps filled from an outside document | 38/38 |
| False alarms (flagged, no planted conflict) | 0 |
| School forms with complete immunizations across clinics | 10/10 |

| Concept | Fields | Filled | Accuracy |
|---|---|---|---|
| alp | 78 | 78 | 100.0% |
| alt | 78 | 78 | 100.0% |
| ast | 78 | 78 | 100.0% |
| bili | 77 | 77 | 100.0% |
| creat | 78 | 78 | 100.0% |
| dbp | 78 | 78 | 100.0% |
| glucose | 78 | 78 | 100.0% |
| hgb | 78 | 78 | 100.0% |
| hr | 78 | 78 | 100.0% |
| plat | 77 | 77 | 100.0% |
| sbp | 78 | 78 | 100.0% |
| temp | 77 | 77 | 100.0% |
| wbc | 78 | 78 | 100.0% |
| weight | 78 | 78 | 100.0% |

Oracle mode uses the answer key as the document reader, so document facts are extracted perfectly by construction. It validates coding, unit conversion, the filler, and the verifier. Run with --reader model for real reading numbers.
