from datetime import date, datetime, timezone

from dayzero.rules import assess, day_zero, merge_snapshots
from dayzero.schema import Drug, Evidence, Extraction, Patient, Reaction, Reporter, Seriousness, Snapshot


def ext(patient=True, reporter=True, drug=True, event=True, death=False, hosp=False):
    return Extraction(language="en", is_followup=False, followup_reference=None,
                      patient=Patient(identifiable=patient, initials="J.K." if patient else None, age=64 if patient else None, sex="M" if patient else "unknown", evidence=[]),
                      reporter=Reporter(identifiable=reporter, name="Dr. Lee" if reporter else None, qualification="physician" if reporter else "unknown", contact=None, evidence=[]),
                      drugs=[Drug(name="Venclexta", role="suspect", dose=None, start_date=None, evidence=[])] if drug else [],
                      reactions=[Reaction(term="septic shock", onset_date=None, outcome="fatal" if death else "unknown", evidence=[])] if event else [],
                      seriousness=Seriousness(death=death, life_threatening=False, hospitalization=hosp, disability=False, congenital_anomaly=False, other_medically_important=False, evidence=[]),
                      event_date=None, summary="", missing_information=[])


def snap(e, day, mid="m1"):
    return Snapshot(message_id=mid, received_at=datetime(2026, 10, day, 9, tzinfo=timezone.utc), extraction=e)


def test_validity_needs_all_four(coder):
    for missing_kw, label in (("patient", "identifiable_patient"), ("reporter", "identifiable_reporter"), ("drug", "suspect_drug"), ("event", "adverse_event")):
        s = merge_snapshots("c", [snap(ext(**{missing_kw: False}), 1)], coder)
        a = assess(s, {}, coder)
        assert not a.valid and a.missing == [label] and a.day_zero is None and a.due_date is None
        assert a.followup_questions, "a missing criterion must draft a question"


def test_day_zero_moves_to_followup(coder):
    snaps = [snap(ext(reporter=False), 1, "m1"), snap(ext(patient=False, drug=False, event=False, reporter=True), 3, "m2")]
    assert day_zero(snaps, coder) == date(2026, 10, 3)
    a = assess(merge_snapshots("c", snaps, coder), {}, coder)
    assert a.valid and a.day_zero == date(2026, 10, 3)


def test_clock_7_days_for_fatal_15_otherwise(coder):
    fatal = assess(merge_snapshots("c", [snap(ext(death=True), 1)], coder), {}, coder)
    assert fatal.serious and fatal.clock_days == 7 and fatal.due_date == date(2026, 10, 8) and "death" in fatal.criteria
    hosp = assess(merge_snapshots("c", [snap(ext(hosp=True), 1)], coder), {}, coder)
    assert hosp.clock_days == 15 and hosp.due_date == date(2026, 10, 16)
    nonserious = assess(merge_snapshots("c", [snap(ext(), 1)], coder), {}, coder)
    assert not nonserious.serious and nonserious.due_date is None


def test_expectedness_uses_rsi(coder):
    s = merge_snapshots("c", [snap(ext(hosp=True), 1)], coder)
    assert assess(s, {"venclexta": ["Septic shock"]}, coder).expectedness == "expected"
    assert assess(s, {"venclexta": ["Nausea"]}, coder).expectedness == "unexpected"
    assert assess(s, {}, coder).expectedness == "unknown"
    assert assess(s, {"venclexta": ["Septic shock"]}, coder).expedited is False   # serious but expected: not an expedited report
    assert assess(s, {}, coder).expedited is True                              # unknown treated conservatively
