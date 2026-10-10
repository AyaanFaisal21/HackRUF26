## Evaluation (oracle)

Messages: 87  Cases: 71

| Field | Accuracy |
|---|---|
| patient.identifiable | 100.0% |
| reporter.identifiable | 100.0% |
| patient.age | 100.0% |
| patient.sex | 100.0% |
| suspect_drugs | 100.0% |
| reactions | 100.0% |
| seriousness | 100.0% |
| is_followup | 100.0% |

Validity decision accuracy: 100.0%
Day zero accuracy: 100.0%
Follow-ups attached to the right case: 15/16
Planted duplicates surfaced: 11/11 (false positive pairs: 14)

Oracle mode uses the answer key as the extractor, so field accuracy is 100% by construction. It validates everything downstream of extraction. Run with DAYZERO_EXTRACTOR=claude for real extraction numbers.
