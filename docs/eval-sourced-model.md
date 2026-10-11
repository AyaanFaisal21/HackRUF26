## Evaluation (reader: model)

Patients scored: 60. Fields with a known truth: 1009.

| Metric | Value |
|---|---|
| Fields filled automatically | 100.0% |
| Accuracy of filled fields | 100.0% |
| Filled fields with a receipt | 100.0% |
| Planted conflicts caught by the verifier | 35/35 |
| Unit traps converted correctly | 12/12 |
| Gaps filled from an outside document | 32/32 |
| False alarms (flagged, no planted conflict) | 0 |
| School forms with complete immunizations across clinics | 10/10 |

| Concept | Fields | Filled | Accuracy |
|---|---|---|---|
| alp | 72 | 72 | 100.0% |
| alt | 72 | 72 | 100.0% |
| ast | 72 | 72 | 100.0% |
| bili | 71 | 71 | 100.0% |
| creat | 72 | 72 | 100.0% |
| dbp | 73 | 73 | 100.0% |
| glucose | 71 | 71 | 100.0% |
| hgb | 72 | 72 | 100.0% |
| hr | 73 | 73 | 100.0% |
| plat | 72 | 72 | 100.0% |
| sbp | 73 | 73 | 100.0% |
| temp | 71 | 71 | 100.0% |
| wbc | 72 | 72 | 100.0% |
| weight | 73 | 73 | 100.0% |

### Document reading: scripts baseline versus reader (model:openai:gpt-4.1)

| Document kind | Docs | Truth facts | Scripts recall | Scripts precision | Reader recall | Reader precision | Reader quotes not located |
|---|---|---|---|---|---|---|---|
| lab_report | 79 | 783 | 57.5% | 100.0% | 100.0% | 100.0% | 0.0% |
| all variant layouts | 88 | 686 | 0.7% | 100.0% | 100.0% | 99.1% | 0.0% |
| clinic_note | 80 | 595 | 39.2% | 100.0% | 100.0% | 99.7% | 0.0% |
| all standard layouts | 120 | 983 | 74.1% | 100.0% | 100.0% | 99.3% | 0.0% |
| pharmacy_list | 29 | 155 | 0.0% | - | 100.0% | 100.0% | 0.0% |
| immunization_record | 10 | 60 | 33.3% | 100.0% | 100.0% | 100.0% | 0.0% |
| urgent_care_note | 10 | 76 | 39.5% | 100.0% | 100.0% | 87.4% | 0.0% |
| all | 208 | 1669 | 43.9% | 100.0% | 100.0% | 99.2% | 0.0% |

Scripts baseline: hand-written label and value patterns for these document layouts. Precision counts extra facts the reader found that are not in the answer key; a date of birth read from a header counts as extra.
