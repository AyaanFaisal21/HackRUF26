"""The structured trial stream: subjects, lab results, adverse events, and daily self-reported symptom diaries.

Real part: CDISC pilot subjects, labs, events (data/samples/trial_cdiscpilot01.json, arm removed).
Synthetic part: calendar dates, daily diaries, and planted patterns with an answer key.
Flags: each one carries a logic chain a physician can read line by line."""
from __future__ import annotations

import json
import random
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIARY_ITEMS = ["nausea", "fatigue", "headache", "rash", "diarrhea", "dizziness", "appetite loss", "sleep problems"]
# CTCAE v5 cut points in multiples of ULN: grade 1 above ULN up to first, grade 2 up to second, grade 3 up to third, grade 4 beyond
CTCAE = {"ALT": (3, 5, 20), "AST": (3, 5, 20), "BILI": (1.5, 3, 10), "ALP": (2.5, 5, 20), "CREAT": (1.5, 3, 6)}
CITE_HY = "FDA Guidance for Industry, Drug-Induced Liver Injury: Premarketing Clinical Evaluation (2009), Hy's Law"
CITE_CTCAE = "NCI CTCAE v5.0, Investigations: ALT/AST/bilirubin/ALP increased"
CITE_PRO = "NCI PRO-CTCAE: patient-reported symptom severity, 0 none to 4 very severe"
CITE_E2A = "ICH E2A: an event is serious if fatal, life-threatening, requires hospitalization, causes disability, or is otherwise medically important"


def ctcae_grade(test: str, x_uln: float) -> int:
    if x_uln is None or x_uln <= 1:
        return 0
    cuts = CTCAE.get(test, (3, 5, 20))
    return 1 + sum(x_uln > c for c in cuts)


def load_trial(path: Path | str | None = None) -> dict:
    return json.load(open(path or ROOT / "data/samples/trial_cdiscpilot01.json"))


def assign_dates(trial: dict, seed: int, today: date) -> None:
    """Give every subject a synthetic day-1 date so study days become calendar dates. Trial is 'ongoing'."""
    rng = random.Random(seed)
    first = today - timedelta(days=240)
    last_lab = defaultdict(int)
    for r in trial["labs"]:
        last_lab[r["subject"]] = max(last_lab[r["subject"]], r["day"])
    for s in trial["subjects"]:
        s["ref_date"] = (first + timedelta(days=rng.randint(0, 150))).isoformat()
        on_study = (today - date.fromisoformat(s["ref_date"])).days + 1
        s["last_day"] = max(1, min(182, on_study, max(last_lab[s["id"]], 1) if last_lab[s["id"]] else on_study))


def day_to_date(subject: dict, day: int) -> date:
    return date.fromisoformat(subject["ref_date"]) + timedelta(days=day - 1)


def plant_lab_signals(trial: dict, seed: int) -> list[dict]:
    """Three Hy's Law patterns over three consecutive visits, one site with slow ALT drift. Values are rewritten in place."""
    rng = random.Random(seed)
    by_subj = defaultdict(list)
    for r in trial["labs"]:
        by_subj[r["subject"]].append(r)
    eligible = [s for s, rows in by_subj.items() if len({r["day"] for r in rows if r["day"] > 1}) >= 6]
    truth = []
    for s in rng.sample(eligible, 3):
        days = sorted({r["day"] for r in by_subj[s] if r["day"] > 1})[2:5]
        mult = {"ALT": [rng.uniform(3.5, 4.5), rng.uniform(5.5, 8), rng.uniform(3, 4)],
                "AST": [rng.uniform(3, 4), rng.uniform(4.5, 6), rng.uniform(2.5, 3.5)],
                "BILI": [rng.uniform(1.2, 1.6), rng.uniform(2.2, 3.2), rng.uniform(1.8, 2.4)]}
        for r in by_subj[s]:
            if r["day"] in days and r["test"] in mult:
                r["value"] = round(mult[r["test"]][days.index(r["day"])] * r["uln"], 1)
        truth.append({"type": "HYS_LAW", "subject": s, "days": days})
    sites = defaultdict(set)
    for s in trial["subjects"]:
        sites[s["site"]].add(s["id"])
    site = sorted(sites, key=lambda k: -len(sites[k]))[2]
    for r in trial["labs"]:
        if r["subject"] in sites[site] and r["test"] == "ALT" and r["day"] > 1:
            r["value"] = round(r["value"] * (1 + 0.012 * r["day"]), 1)
    truth.append({"type": "SITE_DRIFT", "site": site})
    return truth


def gen_diaries(trial: dict, seed: int, lab_truth: list[dict]) -> tuple[list[dict], list[dict]]:
    """Daily 0-4 severity per item per subject. Baselines are low; planted: persistent grade 3+ episodes, sudden jumps,
    and a prodrome (nausea, fatigue, appetite) in the week before each planted liver spike."""
    rng = random.Random(seed + 1)
    rows, truth = [], []
    subj = {s["id"]: s for s in trial["subjects"]}
    hys_by_subject = {t["subject"]: t["days"] for t in lab_truth if t["type"] == "HYS_LAW"}
    candidates = [s["id"] for s in trial["subjects"] if s["last_day"] >= 40 and s["id"] not in hys_by_subject]
    persistent = {s: (rng.choice(DIARY_ITEMS), rng.randint(15, 30)) for s in rng.sample(candidates, 5)}
    jumps = {s: (rng.choice(DIARY_ITEMS), rng.randint(10, 35)) for s in rng.sample([c for c in candidates if c not in persistent], 3)}
    for s in trial["subjects"]:
        sid = s["id"]
        base = {it: rng.choices([0, 1, 2], weights=[0.65, 0.28, 0.07])[0] for it in DIARY_ITEMS}
        spike_day = None
        for day in range(1, s["last_day"] + 1):
            for it in DIARY_ITEMS:
                v = base[it] + rng.choices([-1, 0, 1], weights=[0.15, 0.7, 0.15])[0]
                if rng.random() < 0.02:
                    v += 2
                if sid in persistent and it == persistent[sid][0] and persistent[sid][1] <= day < persistent[sid][1] + 9:
                    v = max(v, rng.choice([3, 3, 4]))
                if sid in jumps and it == jumps[sid][0] and jumps[sid][1] <= day < jumps[sid][1] + 3:
                    v = max(v, max(3, base[it] + 2) + rng.choice([0, 1]))
                if sid in hys_by_subject and it in ("nausea", "fatigue", "appetite loss"):
                    d0 = hys_by_subject[sid][0]
                    if d0 - 7 <= day <= d0 + 3:
                        v = max(v, rng.choice([2, 3, 3]))
                rows.append({"subject": sid, "day": day, "date": day_to_date(s, day).isoformat(), "item": it, "grade": max(0, min(4, v))})
    truth += [{"type": "DIARY_PERSISTENT", "subject": s, "item": it, "day": d} for s, (it, d) in persistent.items()]
    truth += [{"type": "DIARY_JUMP", "subject": s, "item": it, "day": d} for s, (it, d) in jumps.items()]
    truth += [{"type": "DIARY_PRODROME", "subject": s, "day": days[0] - 7} for s, days in hys_by_subject.items()]
    return rows, truth


def compute_flags(trial: dict, diaries: list[dict]) -> list[dict]:
    """Rules over labs and diaries. One flag per episode (same rule, same subject, 14-day gap)."""
    subj = {s["id"]: s for s in trial["subjects"]}
    flags: list[dict] = []

    def fire(subject, rule, severity, day, title, citation, logic, evidence, site=None):
        for f in flags:
            if f["rule"] == rule and f["subject"] == subject and abs(f["day"] - day) <= (28 if rule.startswith(("HYS", "LAB")) else 14):
                return
        s = subj.get(subject)
        flags.append({"id": f"FLG-{len(flags) + 1:04d}", "trial": trial["trial"]["id"], "subject": subject, "site": site or (s["site"] if s else None),
                      "rule": rule, "severity": severity, "day": day, "fired_on": day_to_date(s, day).isoformat() if s else None,
                      "title": title, "citation": citation, "logic": logic, "evidence": evidence, "status": "open"})

    # labs
    by_subj = defaultdict(list)
    for r in trial["labs"]:
        by_subj[r["subject"]].append({**r, "x_uln": round(r["value"] / r["uln"], 2) if r["uln"] else None})
    for sid, rows in by_subj.items():
        s = subj[sid]
        rows.sort(key=lambda r: r["day"])
        baseline = {t: next((r["x_uln"] for r in rows if r["test"] == t and r["day"] <= 1), None) for t in CTCAE}
        days = sorted({r["day"] for r in rows if r["day"] > 1})
        for d in days:
            win = [r for r in rows if d - 7 <= r["day"] <= d]
            peak = {}
            for r in win:
                if r["x_uln"] is not None and r["x_uln"] > peak.get(r["test"], (0, None))[0]:
                    peak[r["test"]] = (r["x_uln"], r)
            at = {r["test"]: r for r in rows if r["day"] == d}
            amino = max(peak.get("ALT", (0, None))[0], peak.get("AST", (0, None))[0])
            bili = peak.get("BILI", (0, None))[0]
            alp = peak.get("ALP", (0, None))[0]
            if amino >= 3 and bili >= 2:
                ev = [peak[t][1] for t in ("ALT", "AST", "BILI", "ALP") if t in peak]
                logic = [f"{r['test']} {r['value']} {r['unit']} on {day_to_date(s, r['day'])} = {r['x_uln']}x ULN (ULN {r['uln']})" for r in ev]
                logic.append(f"ALT or AST >= 3x ULN and total bilirubin >= 2x ULN within 7 days: Hy's Law pattern")
                logic.append(f"ALP {alp}x ULN: {'cholestatic pattern, weighs against Hy\'s Law' if alp >= 2 else 'not cholestatic, consistent with hepatocellular injury'}")
                if baseline.get("ALT") is not None:
                    logic.append(f"Baseline ALT {baseline['ALT']}x ULN on day <= 1: {'new finding' if baseline['ALT'] < 1 else 'abnormal at baseline, consider pre-existing cause'}")
                logic.append("Hy's Law cases carry roughly 10% mortality in the FDA guidance; needs same-day physician review")
                fire(sid, "HYS_LAW", "urgent", d, f"Hy's Law pattern: ALT {peak.get('ALT', (0,))[0]}x ULN, bilirubin {bili}x ULN", CITE_HY, logic, ev)
            for t, r in at.items():
                g = ctcae_grade(t, r["x_uln"])
                if g >= 3 and t != "CREAT":
                    fire(sid, "LAB_GRADE3", "review", d, f"{t} grade {g}: {r['x_uln']}x ULN", CITE_CTCAE,
                         [f"{t} {r['value']} {r['unit']} on {day_to_date(s, d)} = {r['x_uln']}x ULN", f"CTCAE v5 grade {g} (cut points {CTCAE[t]} x ULN)",
                          f"Prior value: {next((q['x_uln'] for q in reversed(rows) if q['test'] == t and q['day'] < d), 'none')}x ULN"], [r])
    # diaries
    by_item = defaultdict(list)
    for r in diaries:
        by_item[(r["subject"], r["item"])].append(r)
    for (sid, it), rows in by_item.items():
        s = subj[sid]
        rows.sort(key=lambda r: r["day"])
        grades = [r["grade"] for r in rows]
        for i in range(6, len(rows)):
            last7 = grades[i - 6: i + 1]
            if sum(g >= 3 for g in last7) >= 5:
                fire(sid, "DIARY_PERSISTENT", "review", rows[i]["day"], f"{it} severe for {sum(g >= 3 for g in last7)} of the last 7 days", CITE_PRO,
                     [f"Self-reported {it} grades over the last 7 days: {last7}", "Rule: grade >= 3 on at least 5 of 7 consecutive days",
                      f"Subject's usual level for {it}: {round(sum(grades[:14]) / max(1, len(grades[:14])), 1)}",
                      "Persistent severe patient-reported symptom: ask the site whether an adverse event was recorded"], rows[i - 6: i + 1])
            if i >= 8:
                prev = sorted(grades[i - 8: i - 1])[3]
                if grades[i - 1] >= max(3, prev + 2) and grades[i] >= max(3, prev + 2):
                    fire(sid, "DIARY_JUMP", "watch", rows[i]["day"], f"{it} jumped from {prev} to {grades[i]}", CITE_PRO,
                         [f"Median {it} over the prior week: {prev}", f"Then {grades[i-1]} and {grades[i]} on two consecutive days",
                          "Rule: increase of at least 2 grades, reaching grade 3 or more, sustained for 2 days"], rows[i - 8: i + 1])
    # site drift
    site_rows = defaultdict(list)
    for sid, rows in by_subj.items():
        for r in rows:
            if r["test"] == "ALT" and r["day"] > 1 and r["x_uln"] is not None:
                site_rows[subj[sid]["site"]].append((r["day"], r["x_uln"]))
    slopes = {}
    for site, pts in site_rows.items():
        if len({p[0] for p in pts}) < 4 or len(pts) < 12:
            continue
        n = len(pts); mx = sum(p[0] for p in pts) / n; my = sum(p[1] for p in pts) / n
        sxx = sum((p[0] - mx) ** 2 for p in pts)
        slopes[site] = (sum((p[0] - mx) * (p[1] - my) for p in pts) / sxx * 100) if sxx else 0.0
    if len(slopes) >= 4:
        vals = sorted(slopes.values()); med = vals[len(vals) // 2]
        mad = sorted(abs(v - med) for v in vals)[len(vals) // 2] or 1e-6
        for site, sl in slopes.items():
            z = (sl - med) / (1.4826 * mad)
            if z > 3:
                flags.append({"id": f"FLG-{len(flags) + 1:04d}", "trial": trial["trial"]["id"], "subject": None, "site": site, "rule": "SITE_DRIFT",
                              "severity": "watch", "day": None, "fired_on": None, "title": f"Site {site}: ALT rising across subjects",
                              "citation": "ICH E6(R3) risk-based quality management: centralized monitoring of site-level trends",
                              "logic": [f"Site {site} ALT slope: +{sl:.2f}x ULN per 100 study days across {len({p for p in site_rows[site]})} results",
                                        f"Median site slope: {med:.2f}; robust z-score {z:.1f}", "Rule: z > 3 against the other sites",
                                        "Possible causes: assay drift at the local lab, a dosing error, or a real safety signal; verify the lab first"],
                              "evidence": [], "status": "open"})
    return flags


def build_trial_bundle(seed: int = 7, today: date | None = None) -> dict:
    today = today or date.today()
    trial = load_trial()
    assign_dates(trial, seed, today)
    lab_truth = plant_lab_signals(trial, seed)
    diaries, diary_truth = gen_diaries(trial, seed, lab_truth)
    flags = compute_flags(trial, diaries)
    return {"trial": trial, "diaries": diaries, "flags": flags, "truth": lab_truth + diary_truth}
