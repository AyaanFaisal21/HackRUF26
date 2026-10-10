"""Deterministic case logic. No model calls. Every function returns the regulation it applied.

Validity:     ICH E2D(R1) section 2.1, four minimum criteria for a valid ICSR.
Seriousness:  ICH E2A section II.B, 21 CFR 312.32(a).
Deadlines:    21 CFR 312.32(c)(1) 15 calendar days for serious and unexpected;
              21 CFR 312.32(c)(2) 7 calendar days for fatal or life-threatening and unexpected.
Day zero:     the first day any employee of the sponsor has all four minimum criteria (ICH E2D 3.2 / E2A).
"""
from __future__ import annotations

from datetime import date, timedelta

from .schema import (Assessment, CaseState, CodedReaction, Drug, Extraction, Patient, Reporter, Seriousness, Snapshot)

FATAL_OR_LT_DAYS = 7
SERIOUS_DAYS = 15
CITE_VALIDITY = "ICH E2D(R1) 2.1: identifiable patient, identifiable reporter, suspect product, adverse event"
CITE_SERIOUS = "ICH E2A II.B / 21 CFR 312.32(a): death, life-threatening, hospitalization, disability, congenital anomaly, other medically important"
CITE_7 = "21 CFR 312.32(c)(2): fatal or life-threatening unexpected suspected adverse reaction, 7 calendar days"
CITE_15 = "21 CFR 312.32(c)(1): serious and unexpected suspected adverse reaction, 15 calendar days"
CITE_DAY0 = "ICH E2D 3.2: the clock starts on the day the sponsor first holds the minimum information"

FOLLOWUP_QUESTIONS = {
    "identifiable_patient": "Could you provide an identifier for the patient, such as initials, age, or sex, so we can distinguish this case from others?",
    "identifiable_reporter": "Could you share the name and contact details of the person reporting this event, so we can follow up if needed?",
    "suspect_drug": "Which product do you believe may be associated with the event? Please include the product name and, if known, the dose and start date.",
    "adverse_event": "Could you describe what happened to the patient, including when it started and the current outcome?",
}

SERIOUS_FIELDS = ("death", "life_threatening", "hospitalization", "disability", "congenital_anomaly", "other_medically_important")


def merge_snapshots(case_id: str, snapshots: list[Snapshot], coder=None) -> CaseState:
    """Union of all snapshots in received order. Booleans OR, lists union by lowercase key, scalars first non-null."""
    snaps = sorted(snapshots, key=lambda s: s.received_at)
    pat = Patient(identifiable=False, initials=None, age=None, sex="unknown", evidence=[])
    rep = Reporter(identifiable=False, name=None, qualification="unknown", contact=None, evidence=[])
    ser = Seriousness(**{f: False for f in SERIOUS_FIELDS}, evidence=[])
    drugs: dict[str, Drug] = {}
    reactions: dict[str, CodedReaction] = {}
    event_date = None
    for s in snaps:
        e = s.extraction
        pat = Patient(identifiable=pat.identifiable or e.patient.identifiable, initials=pat.initials or e.patient.initials,
                      age=pat.age if pat.age is not None else e.patient.age,
                      sex=pat.sex if pat.sex != "unknown" else e.patient.sex, evidence=pat.evidence + e.patient.evidence)
        rep = Reporter(identifiable=rep.identifiable or e.reporter.identifiable, name=rep.name or e.reporter.name,
                       qualification=rep.qualification if rep.qualification != "unknown" else e.reporter.qualification,
                       contact=rep.contact or e.reporter.contact, evidence=rep.evidence + e.reporter.evidence)
        ser = Seriousness(**{f: getattr(ser, f) or getattr(e.seriousness, f) for f in SERIOUS_FIELDS}, evidence=ser.evidence + e.seriousness.evidence)
        for d in e.drugs:
            drugs.setdefault(d.name.strip().lower(), d)
        for r in e.reactions:
            coded = coder.code(r.term) if coder else (None, 0.0)
            key = (coded[0] or r.term).strip().lower()
            if key not in reactions:
                reactions[key] = CodedReaction(term=r.term, pt=coded[0], score=coded[1], outcome=r.outcome, onset_date=r.onset_date)
        event_date = event_date or e.event_date
    return CaseState(case_id=case_id, snapshots=snaps, patient=pat, reporter=rep, drugs=list(drugs.values()),
                     reactions=list(reactions.values()), seriousness=ser, event_date=event_date)


def validity(state: CaseState) -> tuple[bool, list[str]]:
    missing = []
    if not state.patient.identifiable:
        missing.append("identifiable_patient")
    if not state.reporter.identifiable:
        missing.append("identifiable_reporter")
    if not any(d.role == "suspect" for d in state.drugs):
        missing.append("suspect_drug")
    if not state.reactions:
        missing.append("adverse_event")
    return (not missing), missing


def seriousness(state: CaseState) -> tuple[bool, list[str]]:
    crit = [f for f in SERIOUS_FIELDS if getattr(state.seriousness, f)]
    if any(r.outcome == "fatal" for r in state.reactions) and "death" not in crit:
        crit.insert(0, "death")
    return bool(crit), crit


def expectedness(state: CaseState, rsi: dict[str, list[str]]) -> str:
    """expected if every coded reaction is listed for at least one suspect product in the reference safety information.
    unknown if no suspect product has RSI loaded. Unknown is treated as unexpected downstream (conservative)."""
    suspects = [d.name.strip().lower() for d in state.drugs if d.role == "suspect"]
    listed = [rsi[s] for s in suspects if s in rsi]
    if not listed:
        return "unknown"
    expected_terms = {t.lower() for lst in listed for t in lst}
    pts = [(r.pt or r.term).lower() for r in state.reactions]
    if not pts:
        return "unknown"
    return "expected" if all(p in expected_terms for p in pts) else "unexpected"


def day_zero(snapshots: list[Snapshot], coder=None) -> date | None:
    """First received date on which the merged prefix of snapshots meets all four criteria."""
    snaps = sorted(snapshots, key=lambda s: s.received_at)
    for i in range(len(snaps)):
        ok, _ = validity(merge_snapshots("tmp", snaps[: i + 1], coder))
        if ok:
            return snaps[i].received_at.date()
    return None


def followup_questions(state: CaseState, missing: list[str]) -> list[str]:
    qs = [FOLLOWUP_QUESTIONS[m] for m in missing]
    if state.reactions and all(r.onset_date is None for r in state.reactions) and not state.event_date:
        qs.append("When did the event start?")
    if state.reactions and all(r.outcome == "unknown" for r in state.reactions):
        qs.append("What is the patient's current condition, and has the event resolved?")
    if any(d.role == "suspect" and not d.dose for d in state.drugs):
        qs.append("What dose and schedule was the patient taking, and when did they start?")
    return qs


def assess(state: CaseState, rsi: dict[str, list[str]] | None = None, coder=None) -> Assessment:
    rsi = rsi or {}
    valid, missing = validity(state)
    serious, criteria = seriousness(state)
    exp = expectedness(state, rsi)
    dz = day_zero(state.snapshots, coder)
    expedited = serious and exp in ("unexpected", "unknown") and valid
    cites = [CITE_VALIDITY, CITE_SERIOUS]
    clock = due = None
    if expedited and dz:
        clock = FATAL_OR_LT_DAYS if (state.seriousness.death or state.seriousness.life_threatening or "death" in criteria) else SERIOUS_DAYS
        due = dz + timedelta(days=clock)
        cites += [CITE_DAY0, CITE_7 if clock == 7 else CITE_15]
    return Assessment(valid=valid, missing=missing, serious=serious, criteria=criteria, expectedness=exp, expedited=expedited,
                      day_zero=dz, due_date=due, clock_days=clock, citations=cites, followup_questions=followup_questions(state, missing))
