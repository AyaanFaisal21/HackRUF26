"""Duplicate detection = structured field agreement + semantic similarity. Both halves are shown to the human."""
from __future__ import annotations

from datetime import date

from .embed import cosine
from .schema import CaseState, DuplicateCandidate

WEIGHTS = {"sex": 0.05, "age": 0.15, "drug": 0.30, "event": 0.40, "event_date": 0.10}
LIKELY, POSSIBLE = 0.80, 0.62


def _jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if (a | b) else 0.0


def _d(s: str | None) -> date | None:
    try:
        return date.fromisoformat(s[:10]) if s else None
    except ValueError:
        return None


def structured_score(a: CaseState, b: CaseState) -> tuple[float, dict[str, float]]:
    ev = {}
    ev["sex"] = 1.0 if a.patient.sex != "unknown" and a.patient.sex == b.patient.sex else 0.0
    ev["age"] = 1.0 if a.patient.age and b.patient.age and abs(a.patient.age - b.patient.age) <= 2 else 0.0
    ev["drug"] = _jaccard({d.name.lower() for d in a.drugs if d.role == "suspect"}, {d.name.lower() for d in b.drugs if d.role == "suspect"})
    ev["event"] = _jaccard({(r.pt or r.term).lower() for r in a.reactions}, {(r.pt or r.term).lower() for r in b.reactions})
    da, db = _d(a.event_date), _d(b.event_date)
    ev["event_date"] = 1.0 if da and db and abs((da - db).days) <= 3 else 0.0
    return round(sum(WEIGHTS[k] * ev[k] for k in WEIGHTS), 3), ev


def combined(a: CaseState, b: CaseState, emb_a: list[float] | None, emb_b: list[float] | None) -> DuplicateCandidate | None:
    s, ev = structured_score(a, b)
    sem = cosine(emb_a, emb_b) if emb_a and emb_b else 0.0
    score = round(0.7 * s + 0.3 * max(sem, 0.0), 3)
    if score < POSSIBLE:
        return None
    return DuplicateCandidate(case_id=a.case_id, other_case_id=b.case_id, score=score, structured=s, semantic=round(sem, 3),
                              evidence=ev, verdict="likely" if score >= LIKELY else "possible")
