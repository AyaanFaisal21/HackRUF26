"""Pre-Flight core check on a real protocol: every endpoint timepoint must have its measurement in the SoA. Then inject a defect and re-run."""
import json, re, copy
soa = json.load(open("data/soa_parsed.json"))

# endpoints as the LLM-extraction step would hand them over (hand-transcribed from the synopsis text printed by the spike)
endpoints = {
 "dulaglutide_NCT03495102.pdf": [
   {"id":"E1","type":"primary","measure":"HbA1c","week":36,"source":"Synopsis p.18: 'primary endpoint at 36 weeks' / change in HbA1c from baseline"},
   {"id":"E2","type":"secondary","measure":"HbA1c","week":52,"source":"Synopsis p.19: 'secondary outcome measures at 52 weeks'"},
   {"id":"E3","type":"secondary","measure":"Weight","week":36,"source":"Objectives table p.19: change in body weight through 36 weeks"}],
 "tirzepatide_NCT03131687.pdf": [
   {"id":"E1","type":"primary","measure":"HbA1c","week":26,"source":"Synopsis p.9: 'change in HbA1c from baseline to 26 weeks'"},
   {"id":"E2","type":"secondary","measure":"Weight","week":26,"source":"Synopsis: body weight change to 26 weeks"}],
}
ALIAS = {"HbA1c": ["hba1c"], "Weight": ["weight"]}

def check(name, soa_doc, eps):
    acts = soa_doc["activities"]; findings = []
    for e in eps:
        rows = [a for a in acts if any(k in a["activity"].lower() for k in ALIAS[e["measure"]])]
        weeks = sorted({int(w) for a in rows for w in a["at"] if re.fullmatch(r"-?\d+", w)})
        ok = e["week"] in weeks
        findings.append({"endpoint": e["id"], "severity": "ok" if ok else "critical", "check": "endpoint_timepoint_in_SoA",
            "message": f"{e['type']} endpoint {e['id']} measures {e['measure']} at Week {e['week']}; SoA {'has' if ok else 'has NO'} {e['measure']} assessment at Week {e['week']} (SoA weeks: {weeks})",
            "evidence_A": e["source"], "evidence_B": f"SoA row '{rows[0]['activity']}' marked at weeks {weeks}" if rows else "no SoA row matches",
            "fix": None if ok else f"Add {e['measure']} to the Week {e['week']} visit column, or move endpoint {e['id']} to a week where it is collected"})
    return findings

for name, eps in endpoints.items():
    print(f"\n=== {name}")
    for f in check(name, soa[name], eps): print("  ", f["severity"].upper().ljust(8), f["message"])
    # inject defect: delete the endpoint week from the measurement row (simulates an amendment that dropped a visit)
    bad = copy.deepcopy(soa[name]); e = eps[0]
    for a in bad["activities"]:
        if any(k in a["activity"].lower() for k in ALIAS[e["measure"]]): a["at"] = [w for w in a["at"] if w != str(e["week"])]
    print("   -- after injecting 'Week %d %s removed from SoA':" % (e["week"], e["measure"]))
    for f in check(name, bad, eps[:1]): print("  ", f["severity"].upper().ljust(8), f["message"]); print("      fix:", f["fix"])
