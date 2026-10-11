"""Physician brief: everything relevant to one subject, assembled deterministically, with an optional model-written
narrative that may only restate the assembled facts. The brief never states a conclusion; the physician signs one."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date

from .trials import CITE_E2A, ctcae_grade


def _peak(labs, test):
    rows = [r for r in labs if r["test"] == test and r.get("x_uln") is not None]
    return max(rows, key=lambda r: r["x_uln"]) if rows else None


def build_brief(profile: dict, cohort_flags: list[dict], rsi_terms: list[str], llm=None) -> dict:
    s, labs, diaries, events = profile["subject"], profile["labs"], profile["diaries"], profile["events"]
    # rows may come from the database (subject_id, study_day) or straight from trials.py (subject, day): normalise once
    norm = lambda f: {**f, "subject": f.get("subject", f.get("subject_id")), "day": f.get("day", f.get("study_day"))}
    flags = [norm(f) for f in profile["flags"]]
    cohort_flags = [norm(f) for f in cohort_flags]
    open_flags = [f for f in flags if f["status"] != "dismissed"]
    # lab summary
    lab_lines = []
    for t in ("ALT", "AST", "BILI", "ALP", "CREAT"):
        p = _peak(labs, t)
        if p:
            base = next((r for r in sorted(labs, key=lambda r: r["day"]) if r["test"] == t), None)
            lab_lines.append({"test": t, "peak_x_uln": p["x_uln"], "peak_date": p["date"], "grade": ctcae_grade(t, p["x_uln"]),
                              "baseline_x_uln": base["x_uln"] if base else None})
    # diary summary
    by_item = defaultdict(list)
    for d in diaries:
        by_item[d["item"]].append(d)
    diary_lines = []
    for it, rows in by_item.items():
        rows.sort(key=lambda r: r["day"])
        severe = [r for r in rows if r["grade"] >= 3]
        if severe:
            diary_lines.append({"item": it, "days_severe": len(severe), "first_severe": severe[0]["date"], "last_severe": severe[-1]["date"], "max": max(r["grade"] for r in rows)})
    # events
    ev_lines = sorted([{"term": e["pt"] or e["term"], "start_day": e["start_day"], "end_day": e["end_day"], "severity": e["severity"], "serious": e["serious"]} for e in events],
                      key=lambda e: (e["start_day"] is None, e["start_day"] or 0))
    # cohort context
    rules_here = {f["rule"] for f in open_flags}
    same_rule = Counter(f["rule"] for f in cohort_flags if f["rule"] in rules_here and f["subject"] and f["subject"] != s["id"])
    similar = sorted({f["subject"] for f in cohort_flags if f["rule"] in rules_here and f["subject"] and f["subject"] != s["id"]})[:8]
    # label status
    flagged_terms = [f["title"].split(":")[0] for f in open_flags]
    expected = [t for t in flagged_terms if any(x.lower() in t.lower() for x in rsi_terms)]
    # arguments
    for_rel, against = [], []
    earliest_flag_day = min((f["day"] for f in open_flags if f["day"]), default=None)
    if earliest_flag_day and earliest_flag_day > 1:
        for_rel.append(f"Onset on study day {earliest_flag_day}, after exposure began on day 1 (temporal plausibility)")
    liver_base = [l for l in lab_lines if l["test"] in ("ALT", "AST", "BILI") and l["baseline_x_uln"] and l["baseline_x_uln"] > 1]
    if liver_base:
        against.append("Liver tests already above normal at baseline: " + ", ".join(f"{l['test']} {l['baseline_x_uln']}x" for l in liver_base))
    else:
        for_rel.append("Liver tests normal at baseline; abnormality is new on treatment")
    alp = next((l for l in lab_lines if l["test"] == "ALP"), None)
    if alp and alp["peak_x_uln"] >= 2:
        against.append(f"ALP {alp['peak_x_uln']}x ULN suggests a cholestatic or biliary cause")
    concurrent = [e["term"] for e in ev_lines if e["start_day"] and earliest_flag_day and abs(e["start_day"] - earliest_flag_day) <= 14]
    if concurrent:
        for_rel.append("Concurrent recorded adverse events: " + ", ".join(concurrent[:5]))
    if same_rule:
        for_rel.append("Same pattern seen in other subjects on this trial: " + ", ".join(f"{k} x{v}" for k, v in same_rule.items()))
    else:
        against.append("No other subject on this trial shows the same pattern yet")
    against.append("Dechallenge unknown: no record yet of what happened after dosing stopped")
    against.append("Concomitant medications not loaded; hepatotoxic co-medication cannot be excluded")
    serious_hint = any(f["severity"] == "urgent" for f in open_flags) or any(e["serious"] for e in ev_lines)
    reg = ("If assessed as serious, unexpected, and possibly related: expedited report, 7 days if life-threatening, else 15 days (21 CFR 312.32)"
           if serious_hint else "No seriousness criterion met on current evidence; routine reporting")
    brief = {
        "subject": {"id": s["id"], "site": s["site"], "age": s["age"], "sex": s["sex"], "days_on_study": s["last_day"]},
        "flags": [{"id": f["id"], "rule": f["rule"], "severity": f["severity"], "fired_on": f["fired_on"], "title": f["title"], "citation": f["citation"], "logic": f["logic"]} for f in open_flags],
        "labs": lab_lines, "symptoms": diary_lines, "events": ev_lines,
        "label_status": {"expected_terms_matched": expected, "note": "Expectedness is judged against the investigator's brochure; mock reference list used here"},
        "cohort": {"subjects_with_same_pattern": dict(same_rule), "similar_subjects": similar},
        "arguments_for_relatedness": for_rel, "arguments_against": against,
        "regulatory": {"note": reg, "citation": CITE_E2A},
        "assessment": None, "narrative": None, "generated_on": date.today().isoformat(),
    }
    if llm is not None:
        brief["narrative"] = llm.text(
            "You write the narrative section of a clinical safety brief for a physician. Use only the facts in the JSON. Do not add facts, "
            "do not state a causality conclusion, do not give treatment advice. Four short paragraphs: what happened, the timeline, what argues for and against drug relatedness, what is still unknown.",
            str({k: v for k, v in brief.items() if k not in ("narrative", "assessment")}), max_tokens=900)
    return brief
