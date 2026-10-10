"""Day Zero spike: FAERS -> ground truth -> synthetic messy inbox -> rules -> queue. No LLM needed to run."""
import json, glob, random, sys
from datetime import date, datetime, timedelta
from collections import Counter
from rules import ICSR, validity, seriousness, day_zero, due_date, duplicate_score, merge

random.seed(7)
recs = []
for f in sorted(glob.glob("data/faers_*.json")):
    recs += json.load(open(f))["results"]

def pdate(s):
    try: return datetime.strptime(s, "%Y%m%d").date()
    except Exception: return None

QUAL = {"1":"Physician","2":"Pharmacist","3":"Other health professional","4":"Lawyer","5":"Consumer/non-health professional"}

# ---- 1. normalize FAERS to ground truth and measure field availability
truth, avail = [], Counter()
for r in recs:
    p = r.get("patient", {})
    age = p.get("patientonsetage"); unit = p.get("patientonsetageunit")
    age = int(float(age)) if age and unit == "801" else None
    sex = {"1":"M","2":"F"}.get(p.get("patientsex"))
    drugs = [d.get("medicinalproduct","").title() for d in p.get("drug",[]) if d.get("drugcharacterization")=="1"]
    events = [x["reactionmeddrapt"] for x in p.get("reaction",[])]
    ev_date = pdate((p.get("summary",{}).get("narrativeincludeclinical","") or "").replace("CASE EVENT DATE: ",""))
    c = ICSR(case_id=r["safetyreportid"], received=pdate(r["receivedate"]),
             patient_identifiable=bool(age or sex), patient_age=age, patient_sex=sex,
             reporter_identifiable=True, reporter_qualification=QUAL.get(r.get("primarysource",{}).get("qualification")),
             suspect_drugs=sorted(set(drugs)), events=events, event_date=ev_date,
             death=r.get("seriousnessdeath")=="1", life_threatening=r.get("seriousnesslifethreatening")=="1",
             hospitalization=r.get("seriousnesshospitalization")=="1", disability=r.get("seriousnessdisabling")=="1",
             congenital_anomaly=r.get("seriousnesscongenitalanomali")=="1", other_serious=r.get("seriousnessother")=="1")
    truth.append(c)
    avail["age"] += age is not None; avail["sex"] += sex is not None; avail["event_date"] += ev_date is not None
    avail["has_suspect_drug"] += bool(drugs); avail["reporter_qual"] += c.reporter_qualification is not None
    avail["drugs>5"] += len(p.get("drug",[])) > 5
n = len(truth)
print(f"FAERS records: {n}")
print("field availability:", {k: f"{v/n:.0%}" for k,v in avail.items()})
print("avg suspect drugs/case: %.1f  avg events/case: %.1f" % (sum(len(c.suspect_drugs) for c in truth)/n, sum(len(c.events) for c in truth)/n))
print("seriousness mix:", Counter(tuple(seriousness(c)["criteria"]) for c in truth).most_common(5))
print("distinct MedDRA PTs seen (= free mock dictionary):", len({e for c in truth for e in c.events}))

# ---- 2. synthetic inbox: FAERS has NO names/initials/narratives. We must add them. Answer key kept.
FIRST = ["Maria","James","Priya","Wei","Ahmed","Elena","Tom","Grace","Luis","Hana"]; LAST=["Okafor","Nguyen","Patel","Lee","Garcia","Schmidt","Rossi","Khan","Brown","Silva"]
inbox, key = [], {}
for i, c in enumerate(truth[:200]):
    pt_init = random.choice("ABCDEFGHJKLMNPRST")+random.choice("ABCDEFGHJKLMNPRST")
    rep = f"Dr. {random.choice(FIRST)} {random.choice(LAST)}"
    drop = random.random()
    variant = "complete"
    if drop < 0.10: variant = "no_reporter"
    elif drop < 0.18: variant = "no_patient"
    msg = ICSR(**{**c.__dict__, "case_id": f"MSG-{i:04d}"})
    msg.patient_identifiable = variant != "no_patient"
    msg.reporter_identifiable = variant != "no_reporter"
    # narrative placeholder: the LLM step rewrites this into an email / call note / patient message
    narrative = (f"{'From: '+rep if msg.reporter_identifiable else 'From: (unsigned)'}. "
                 f"{'Patient '+pt_init+', ' if msg.patient_identifiable else 'A patient, '}"
                 f"{str(c.patient_age)+'-year-old ' if c.patient_age and msg.patient_identifiable else ''}{'male' if c.patient_sex=='M' else 'female' if c.patient_sex else ''} "
                 f"on {', '.join(c.suspect_drugs) or 'an unnamed product'} developed {', '.join(e.lower() for e in c.events[:3])}. "
                 f"{'The patient died.' if c.death else 'Hospitalized.' if c.hospitalization else ''}")
    inbox.append({"msg_id": msg.case_id, "received": str(c.received), "channel": random.choice(["email","call_note","patient_portal","fax_pdf"]), "text": narrative})
    key[msg.case_id] = {"truth_case": c.case_id, "variant": variant, "icsr": msg}
    # follow-up that supplies the missing fact 2 days later
    if variant != "complete":
        fu = ICSR(case_id=f"{msg.case_id}-FU", received=c.received + timedelta(days=2), reporter_identifiable=True, patient_identifiable=True)
        key[fu.case_id] = {"truth_case": c.case_id, "variant": "followup", "icsr": fu}
        inbox.append({"msg_id": fu.case_id, "received": str(fu.received), "channel": "email", "text": f"Follow-up: this is {rep}; patient initials {pt_init}."})
# planted duplicates: same case, second reporter, slightly different age
dups = []
for c in random.sample(truth[:200], 20):
    d = ICSR(**{**c.__dict__, "case_id": c.case_id+"-DUP", "patient_age": (c.patient_age+1) if c.patient_age else None, "reporter_qualification": "Consumer/non-health professional"})
    dups.append((c, d))

# ---- 3. run rules on the answer key to prove the queue logic end to end
rows = []
by_case = {}
for mid, k in key.items():
    by_case.setdefault(k["truth_case"], []).append(k["icsr"])
for tc, msgs in by_case.items():
    msgs.sort(key=lambda m: m.received)
    merged = None
    for m in msgs: merged = merge(merged, m)
    dz = day_zero(msgs); v = validity(merged); s = seriousness(merged); dd = due_date(merged, dz)
    rows.append({"case": tc, "msgs": len(msgs), "valid": v["valid"], "missing": v["missing"], "serious": s["criteria"], "day_zero": str(dz), "due": str(dd["due"]) if dd and dd["due"] else None, "clock_days": dd["days"] if dd else None})
print("\nqueue sample (sorted by due date):")
for r in sorted([r for r in rows if r["due"]], key=lambda r: r["due"])[:6]: print(" ", r)
print("not-yet-valid cases awaiting follow-up:", sum(1 for r in rows if not r["valid"]))
print("cases where day zero moved to follow-up date:", sum(1 for tc,m in by_case.items() if len(m)>1 and day_zero(m)==m[-1].received))

# ---- 4. duplicate detection precision/recall on structured records
pos = [duplicate_score(a,b)["score"] for a,b in dups]
neg = [duplicate_score(truth[i], truth[j])["score"] for i in range(0,200,7) for j in range(1,200,11) if i!=j]
for thr in (0.6,0.7,0.8):
    tp = sum(p>=thr for p in pos); fp = sum(q>=thr for q in neg)
    print(f"dup threshold {thr}: recall {tp/len(pos):.2f}  false positives {fp}/{len(neg)} ({fp/len(neg):.1%})")
json.dump(inbox, open("data/synthetic_inbox.json","w"), indent=1, default=str)
json.dump({k:{"truth_case":v["truth_case"],"variant":v["variant"]} for k,v in key.items()}, open("data/answer_key.json","w"), indent=1)
print("\nwrote data/synthetic_inbox.json and data/answer_key.json")
