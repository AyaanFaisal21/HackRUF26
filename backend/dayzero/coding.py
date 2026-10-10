"""Mock MedDRA coder. Real MedDRA is licensed; the preferred-term list ships with openFDA records, so we use the
terms observed in our FAERS sample as the dictionary. Synonyms cover the lay phrasings the generator uses."""
from __future__ import annotations

import json
from pathlib import Path

from rapidfuzz import fuzz, process

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
SYNONYMS = {
    "heart attack": "Myocardial infarction", "stroke": "Cerebrovascular accident", "shortness of breath": "Dyspnoea",
    "trouble breathing": "Dyspnoea", "passed away": "Death", "died": "Death", "throwing up": "Vomiting",
    "feeling sick": "Nausea", "rash": "Rash", "hives": "Urticaria", "blood clot in the lung": "Pulmonary embolism",
    "low platelets": "Thrombocytopenia", "kidney failure": "Acute kidney injury", "liver damage": "Hepatotoxicity",
    "fainted": "Syncope", "seizure": "Seizure", "fever": "Pyrexia", "tiredness": "Fatigue", "very tired": "Fatigue",
    "high blood sugar": "Hyperglycaemia", "low blood sugar": "Hypoglycaemia", "infection in the blood": "Sepsis",
}


class Coder:
    def __init__(self, terms: list[str] | None = None, threshold: float = 82.0):
        if terms is None:
            terms = json.load(open(DATA_DIR / "mock_meddra.json"))["terms"]
        self.terms = sorted(set(terms) | set(SYNONYMS.values()))
        self.threshold = threshold

    def code(self, term: str) -> tuple[str | None, float]:
        t = term.strip().lower()
        if t in SYNONYMS:
            return SYNONYMS[t], 100.0
        hit = process.extractOne(t, self.terms, scorer=fuzz.WRatio, processor=str.lower)
        if hit and hit[1] >= self.threshold:
            return hit[0], float(hit[1])
        return None, float(hit[1]) if hit else 0.0
