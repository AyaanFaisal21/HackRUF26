"""The small shared vocabulary. Every fact is coded to one of these keys so a fax and a FHIR resource compare.
Codes are LOINC where one exists. Units normalise to one canonical unit per concept with the conversions below."""
from __future__ import annotations

import re

from rapidfuzz import fuzz, process

CONCEPTS: dict[str, dict] = {
    "birth_date": dict(display="Date of birth", code="21112-8", kind="demographic", vtype="date"),
    "sex": dict(display="Sex", code="46098-0", kind="demographic", vtype="text"),
    "race": dict(display="Race", code="72826-1", kind="demographic", vtype="text"),
    "sbp": dict(display="Systolic blood pressure", code="8480-6", kind="vital", vtype="number", unit="mmHg", range=(60, 260), tol=2),
    "dbp": dict(display="Diastolic blood pressure", code="8462-4", kind="vital", vtype="number", unit="mmHg", range=(30, 160), tol=2),
    "hr": dict(display="Heart rate", code="8867-4", kind="vital", vtype="number", unit="/min", range=(30, 220), tol=3),
    "temp": dict(display="Body temperature", code="8310-5", kind="vital", vtype="number", unit="Cel", range=(34, 42.5), tol=0.3),
    "weight": dict(display="Body weight", code="29463-7", kind="vital", vtype="number", unit="kg", range=(2, 300), tol=1.0),
    "height": dict(display="Body height", code="8302-2", kind="vital", vtype="number", unit="cm", range=(40, 230), tol=1.0),
    "alt": dict(display="ALT", code="1742-6", kind="lab", vtype="number", unit="U/L", range=(0, 5000), rtol=0.05),
    "ast": dict(display="AST", code="1920-8", kind="lab", vtype="number", unit="U/L", range=(0, 5000), rtol=0.05),
    "bili": dict(display="Total bilirubin", code="1975-2", kind="lab", vtype="number", unit="umol/L", range=(0, 600), rtol=0.05),
    "alp": dict(display="Alkaline phosphatase", code="6768-6", kind="lab", vtype="number", unit="U/L", range=(0, 3000), rtol=0.05),
    "creat": dict(display="Creatinine", code="2160-0", kind="lab", vtype="number", unit="umol/L", range=(10, 2000), rtol=0.05),
    "hgb": dict(display="Hemoglobin", code="718-7", kind="lab", vtype="number", unit="mmol/L", range=(2, 16), rtol=0.05),
    "wbc": dict(display="White blood cells", code="6690-2", kind="lab", vtype="number", unit="10*9/L", range=(0.5, 100), rtol=0.05),
    "plat": dict(display="Platelets", code="777-3", kind="lab", vtype="number", unit="10*9/L", range=(5, 1500), rtol=0.05),
    "glucose": dict(display="Glucose", code="2345-7", kind="lab", vtype="number", unit="mmol/L", range=(1, 60), rtol=0.05),
    "medication": dict(display="Medication", kind="medication", vtype="text"),
    "condition": dict(display="Diagnosis", kind="condition", vtype="text"),
    "adverse_event": dict(display="Adverse event", kind="event", vtype="text"),
    "allergy": dict(display="Allergy", kind="allergy", vtype="text"),
    "immunization": dict(display="Immunization", kind="immunization", vtype="text"),
}
LOINC_TO_KEY = {v["code"]: k for k, v in CONCEPTS.items() if "code" in v}
LOINC_TO_KEY["85354-9"] = "bp_panel"
CDISC_TO_KEY = {"SYSBP": "sbp", "DIABP": "dbp", "PULSE": "hr", "TEMP": "temp", "WEIGHT": "weight", "HEIGHT": "height",
                "ALT": "alt", "AST": "ast", "BILI": "bili", "ALP": "alp", "CREAT": "creat", "HGB": "hgb", "WBC": "wbc", "PLAT": "plat", "GLUC": "glucose"}
SYNONYMS = {
    "systolic blood pressure": "sbp", "systolic": "sbp", "bp systolic": "sbp", "sbp": "sbp",
    "diastolic blood pressure": "dbp", "diastolic": "dbp", "bp diastolic": "dbp", "dbp": "dbp",
    "heart rate": "hr", "pulse": "hr", "pulse rate": "hr", "hr": "hr", "p": "hr", "hr bpm": "hr",
    "temperature": "temp", "temp": "temp", "body temperature": "temp", "t": "temp",
    "weight": "weight", "body weight": "weight", "wt": "weight", "weight kg": "weight", "weight lb": "weight", "height": "height", "ht": "height", "body height": "height",
    "b/p systolic": "sbp", "b/p diastolic": "dbp", "bp sys": "sbp", "bp dia": "dbp", "sys": "sbp", "dia": "dbp", "systolic bp": "sbp", "diastolic bp": "dbp",
    "blood pressure systolic": "sbp", "blood pressure diastolic": "dbp", "systolic pressure": "sbp", "diastolic pressure": "dbp",
    "alt": "alt", "alanine aminotransferase": "alt", "sgpt": "alt", "ast": "ast", "aspartate aminotransferase": "ast", "sgot": "ast",
    "bilirubin": "bili", "total bilirubin": "bili", "bilirubin total": "bili", "alkaline phosphatase": "alp", "alk phos": "alp", "alp": "alp",
    "creatinine": "creat", "serum creatinine": "creat", "hemoglobin": "hgb", "haemoglobin": "hgb", "hgb": "hgb",
    "white blood cells": "wbc", "wbc": "wbc", "leukocytes": "wbc", "white cell count": "wbc", "platelets": "plat", "platelet count": "plat", "plt": "plat",
    "glucose": "glucose", "blood glucose": "glucose", "date of birth": "birth_date", "dob": "birth_date", "sex": "sex", "gender": "sex", "race": "race",
}
CATEGORY_DEFAULT = {"medication": "medication", "condition": "condition", "adverse_event": "adverse_event", "allergy": "allergy", "immunization": "immunization"}

_UNIT_ALIASES = {"mmhg": "mmHg", "mm hg": "mmHg", "bpm": "/min", "beats/min": "/min", "/min": "/min", "min-1": "/min",
                 "c": "Cel", "°c": "Cel", "cel": "Cel", "celsius": "Cel", "deg c": "Cel", "f": "degF", "°f": "degF", "degf": "degF", "fahrenheit": "degF", "deg f": "degF", "b0f": "degF", "b0c": "Cel", "\u00b0f": "degF", "\u00b0c": "Cel",
                 "kg": "kg", "kgs": "kg", "kilograms": "kg", "lb": "lb", "lbs": "lb", "pounds": "lb", "cm": "cm", "in": "in", "inches": "in", "inch": "in", "m": "m",
                 "u/l": "U/L", "iu/l": "U/L", "umol/l": "umol/L", "µmol/l": "umol/L", "mg/dl": "mg/dL", "g/l": "g/L", "g/dl": "g/dL",
                 "10*9/l": "10*9/L", "10^9/l": "10*9/L", "gi/l": "10*9/L", "giga/l": "10*9/L", "x10^9/l": "10*9/L", "k/ul": "10*9/L", "mmol/l": "mmol/L"}


def normalize_unit(u: str | None) -> str | None:
    if not u:
        return None
    t = u.strip().lower().rstrip(".").strip()
    return _UNIT_ALIASES.get(t, u.strip().rstrip("."))


def convert(value: float, from_unit: str | None, to_unit: str | None, concept: str) -> float | None:
    """Convert between units we know. Returns None if no conversion is known."""
    f, t = normalize_unit(from_unit), normalize_unit(to_unit)
    if f == t or t is None or f is None:
        return value
    pair = (f, t)
    simple = {("lb", "kg"): 0.45359237, ("kg", "lb"): 1 / 0.45359237, ("in", "cm"): 2.54, ("cm", "in"): 1 / 2.54, ("m", "cm"): 100.0, ("cm", "m"): 0.01,
              ("g/dL", "g/L"): 10.0, ("g/L", "g/dL"): 0.1}
    if pair in simple:
        return value * simple[pair]
    if pair == ("degF", "Cel"):
        return (value - 32) / 1.8
    if pair == ("Cel", "degF"):
        return value * 1.8 + 32
    if concept == "bili" and pair == ("mg/dL", "umol/L"):
        return value * 17.104
    if concept == "bili" and pair == ("umol/L", "mg/dL"):
        return value / 17.104
    if concept == "creat" and pair == ("mg/dL", "umol/L"):
        return value * 88.42
    if concept == "creat" and pair == ("umol/L", "mg/dL"):
        return value / 88.42
    if concept == "hgb" and pair == ("g/dL", "mmol/L"):
        return value * 0.6206
    if concept == "hgb" and pair == ("mmol/L", "g/dL"):
        return value / 0.6206
    if concept == "glucose" and pair == ("mg/dL", "mmol/L"):
        return value / 18.016
    if concept == "glucose" and pair == ("mmol/L", "mg/dL"):
        return value * 18.016
    return None


_SYN_KEYS = list(SYNONYMS.keys())


def code_concept(label: str, category: str | None = None) -> str | None:
    """Map a label as written to a concept key. Exact synonym, then fuzzy, then the category default."""
    t = re.sub(r"[^a-z0-9/ ]", " ", label.lower()).strip()
    t = re.sub(r"\s+", " ", t)
    if t in SYNONYMS:
        return SYNONYMS[t]
    if category in CATEGORY_DEFAULT:
        return CATEGORY_DEFAULT[category]
    if len(t) < 4:          # one- and two-letter labels are too ambiguous to fuzzy-match
        return None
    hit = process.extractOne(t, [k for k in _SYN_KEYS if len(k) >= 4], scorer=fuzz.WRatio)
    if hit and hit[1] >= 88:
        return SYNONYMS[hit[0]]
    return None


def parse_number(s: str | None) -> float | None:
    if s is None:
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", str(s).replace(",", ""))
    return float(m.group()) if m else None


def numbers_agree(concept: str, a: float, b: float) -> bool:
    c = CONCEPTS.get(concept, {})
    if "tol" in c:
        return abs(a - b) <= c["tol"]
    if "rtol" in c:
        return abs(a - b) <= c["rtol"] * max(abs(a), abs(b), 1e-9)
    return abs(a - b) < 1e-6


def in_range(concept: str, v: float) -> bool:
    r = CONCEPTS.get(concept, {}).get("range")
    return True if not r else r[0] <= v <= r[1]
