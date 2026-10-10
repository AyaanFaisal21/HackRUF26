"""Day Zero deterministic core: validity, seriousness, day zero, deadlines, duplicates.
LLM extracts. Rules decide. Human confirms. Nothing here calls a model."""
from dataclasses import dataclass, field, asdict
from datetime import date, timedelta
from typing import Optional

FATAL_OR_LT_DAYS = 7     # 21 CFR 312.32(c)(2): fatal or life-threatening, 7 calendar days
SERIOUS_DAYS = 15        # 21 CFR 312.32(c)(1): other serious unexpected, 15 calendar days

@dataclass
class ICSR:
    case_id: str
    received: date
    patient_identifiable: bool = False   # initials / age / sex / id present (ICH E2D min criteria)
    patient_age: Optional[int] = None
    patient_sex: Optional[str] = None
    reporter_identifiable: bool = False  # name or contact present
    reporter_qualification: Optional[str] = None
    suspect_drugs: list = field(default_factory=list)
    events: list = field(default_factory=list)
    event_date: Optional[date] = None
    death: bool = False
    life_threatening: bool = False
    hospitalization: bool = False
    disability: bool = False
    congenital_anomaly: bool = False
    other_serious: bool = False
    source_spans: dict = field(default_factory=dict)  # field -> text evidence

def validity(c: ICSR) -> dict:
    missing = []
    if not c.patient_identifiable: missing.append("identifiable_patient")
    if not c.reporter_identifiable: missing.append("identifiable_reporter")
    if not c.suspect_drugs: missing.append("suspect_drug")
    if not c.events: missing.append("adverse_event")
    return {"valid": not missing, "missing": missing, "rule": "ICH E2D(R1) 2.1 minimum criteria"}

def seriousness(c: ICSR) -> dict:
    crit = [k for k in ("death","life_threatening","hospitalization","disability","congenital_anomaly","other_serious") if getattr(c,k)]
    return {"serious": bool(crit), "criteria": crit, "rule": "ICH E2A / 21 CFR 312.32(a)"}

def day_zero(messages: list) -> Optional[date]:
    """messages: chronological list of ICSR snapshots (initial + follow-ups).
    Day zero = first received date on which the merged case meets all four criteria."""
    merged = None
    for m in messages:
        merged = merge(merged, m)
        if validity(merged)["valid"]:
            return m.received
    return None

def merge(a: Optional[ICSR], b: ICSR) -> ICSR:
    if a is None: return ICSR(**asdict(b))
    out = ICSR(**asdict(a))
    for k, v in asdict(b).items():
        cur = getattr(out, k)
        if k in ("suspect_drugs","events"):
            setattr(out, k, sorted(set(cur) | set(v)))
        elif isinstance(v, bool):
            setattr(out, k, cur or v)
        elif v not in (None, "", {}) and cur in (None, "", {}):
            setattr(out, k, v)
    return out

def due_date(c: ICSR, dz: Optional[date]) -> Optional[dict]:
    if dz is None: return None
    s = seriousness(c)
    if not s["serious"]: return {"due": None, "days": None, "rule": "non-serious: periodic reporting"}
    days = FATAL_OR_LT_DAYS if (c.death or c.life_threatening) else SERIOUS_DAYS
    return {"due": dz + timedelta(days=days), "days": days, "rule": f"21 CFR 312.32(c): {days} calendar days from day zero"}

def duplicate_score(a: ICSR, b: ICSR) -> dict:
    """Structured-field similarity. Returns score in [0,1] and the per-field evidence."""
    ev = {}
    ev["sex"] = 1.0 if a.patient_sex and a.patient_sex == b.patient_sex else 0.0
    ev["age"] = 1.0 if a.patient_age and b.patient_age and abs(a.patient_age-b.patient_age) <= 2 else 0.0
    da, db = set(map(str.lower,a.suspect_drugs)), set(map(str.lower,b.suspect_drugs))
    ev["drug"] = len(da & db)/len(da | db) if da|db else 0.0
    ea, eb = set(map(str.lower,a.events)), set(map(str.lower,b.events))
    ev["event"] = len(ea & eb)/len(ea | eb) if ea|eb else 0.0
    ev["event_date"] = 1.0 if a.event_date and b.event_date and abs((a.event_date-b.event_date).days) <= 3 else 0.0
    w = {"sex":0.1,"age":0.2,"drug":0.3,"event":0.3,"event_date":0.1}
    score = sum(w[k]*ev[k] for k in w)
    return {"score": round(score,3), "evidence": ev}
