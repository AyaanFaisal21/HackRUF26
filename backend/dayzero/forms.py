"""Pre-filled expedited report, modelled on the sections of FDA Form 3500A (MedWatch mandatory reporting).
Every field carries its source. A provider verifies and signs; the submission itself is mocked."""
from __future__ import annotations

from datetime import date, timedelta


def _f(label, value, source):
    return {"label": label, "value": value, "source": source}


def form_from_case(rec) -> dict:
    s, a = rec.state, rec.assessment
    reactions = ", ".join(r.pt or r.term for r in s.reactions)
    suspects = [d for d in s.drugs if d.role == "suspect"]
    outcome = [c.replace("_", " ") for c in a.criteria]
    msg_ids = [snap.message_id for snap in s.snapshots]
    src = f"case {s.case_id}, messages {', '.join(msg_ids)}"
    return {
        "source_type": "intake_case", "source_id": s.case_id, "status": "draft", "due_date": a.due_date.isoformat() if a.due_date else None, "clock_days": a.clock_days,
        "sections": {
            "A. Patient information": [_f("Patient identifier", s.patient.initials or "(initials not given)", src), _f("Age", s.patient.age, src), _f("Sex", s.patient.sex, src), _f("Weight", None, "not reported")],
            "B. Adverse event": [_f("Outcomes attributed to event", outcome, "rules: seriousness criteria"), _f("Date of event", s.event_date, src), _f("Date of this report", date.today().isoformat(), "system"),
                                  _f("Describe event", s.snapshots[0].extraction.summary, "extraction summary; verbatim quotes available in case view"),
                                  _f("Relevant tests / laboratory data", None, "none in report"), _f("Other relevant history", None, "none in report")],
            "D. Suspect products": [_f("Name", ", ".join(d.name for d in suspects) or None, src), _f("Dose, frequency, route", ", ".join(d.dose for d in suspects if d.dose) or None, src),
                                    _f("Therapy dates", ", ".join(d.start_date for d in suspects if d.start_date) or None, src), _f("Event abated after use stopped", "unknown", "not reported"), _f("Event reappeared after reintroduction", "unknown", "not reported")],
            "E. Reporter": [_f("Name", s.reporter.name, src), _f("Contact", s.reporter.contact, src), _f("Health professional", s.reporter.qualification not in ("consumer", "unknown", "lawyer"), src), _f("Occupation", s.reporter.qualification, src)],
            "G. Manufacturer / sponsor": [_f("Report type", "initial" if len(s.snapshots) == 1 else "follow-up", "case history"), _f("Report source", "spontaneous" if s.reporter.qualification == "consumer" else "health professional", src),
                                           _f("Expedited timeline", f"{a.clock_days}-day" if a.clock_days else "not expedited", "rules: " + "; ".join(a.citations[-1:])), _f("Day zero", a.day_zero.isoformat() if a.day_zero else None, "rules: day zero")],
        },
        "reactions": reactions, "verified_fields": [], "signed_by": None, "signed_at": None,
    }


def form_from_subject(profile: dict, brief: dict, assessment: dict) -> dict:
    s = profile["subject"]
    flags = brief["flags"]
    labs = "; ".join(f"{l['test']} peak {l['peak_x_uln']}x ULN on {l['peak_date']} (grade {l['grade']})" for l in brief["labs"] if l["grade"] >= 1) or None
    serious = assessment.get("serious", False)
    clock = 7 if assessment.get("life_threatening") or assessment.get("fatal") else 15
    src = f"subject {s['id']} profile; brief {brief['generated_on']}"
    return {
        "source_type": "trial_subject", "source_id": s["id"], "status": "draft",
        "due_date": (date.fromisoformat(assessment["assessed_on"]) + timedelta(days=clock)).isoformat() if serious else None,
        "clock_days": clock if serious else None,
        "sections": {
            "A. Patient information": [_f("Patient identifier", s["id"], "trial subject id (no name held)"), _f("Age", s["age"], src), _f("Sex", s["sex"], src), _f("Weight", None, "vitals not loaded")],
            "B. Adverse event": [_f("Outcomes attributed to event", [k for k in ("fatal", "life_threatening", "hospitalization", "disability", "other_medically_important") if assessment.get(k)], "physician assessment"),
                                  _f("Date of event", flags[0]["fired_on"] if flags else None, flags[0]["id"] if flags else "no flag"), _f("Date of this report", date.today().isoformat(), "system"),
                                  _f("Describe event", "; ".join(f["title"] for f in flags) or assessment.get("event", ""), "flags and physician assessment"),
                                  _f("Relevant tests / laboratory data", labs, "lab timeline"), _f("Other relevant history", "; ".join(e["term"] for e in brief["events"][:6]) or None, "recorded adverse events")],
            "D. Suspect products": [_f("Name", profile["trial"]["product"], "trial record; blinded label, safety team unblinds for submission"), _f("Dose, frequency, route", "per protocol", "protocol"),
                                    _f("Therapy dates", f"study day 1 = {s['ref_date']}", src), _f("Event abated after use stopped", assessment.get("dechallenge", "unknown"), "physician assessment"), _f("Event reappeared after reintroduction", "unknown", "not applicable")],
            "E. Reporter": [_f("Name", assessment.get("physician", "(unsigned)"), "signature"), _f("Contact", f"site {s['site']}", src), _f("Health professional", True, "investigator"), _f("Occupation", "physician", "signature")],
            "G. Manufacturer / sponsor": [_f("Report type", "initial", "system"), _f("Report source", "clinical study", "trial"),
                                           _f("Expedited timeline", f"{clock}-day" if serious else "not expedited", "21 CFR 312.32(c)"), _f("Causality (investigator)", assessment.get("relatedness"), "physician assessment")],
        },
        "reactions": "; ".join(f["title"] for f in flags), "verified_fields": [], "signed_by": None, "signed_at": None,
    }
