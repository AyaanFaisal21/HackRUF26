"""One-time conversion of the CDISC SDTM pilot (XPT) into the compact JSON the app loads.
Drops the treatment arm entirely so nothing downstream can unblind. Needs pandas (system python is fine).
usage: python3 convert_cdisc.py <dir with dm/lb/ae/vs/cm .xpt> <out.json>"""
import json, sys
import pandas as pd

src, out = sys.argv[1], sys.argv[2]
rd = lambda n: pd.read_sas(f"{src}/{n}.xpt", format="xport", encoding="latin1")
dm, lb, ae, vs, cm = rd("dm"), rd("lb"), rd("ae"), rd("vs"), rd("cm")
dm = dm[dm.ARM != "Screen Failure"]
subjects = [{"id": r.USUBJID, "site": str(r.SITEID), "age": int(r.AGE), "sex": r.SEX, "race": r.RACE} for r in dm.itertuples()]
ids = set(dm.USUBJID)

def f(v):
    try: return None if pd.isna(v) else int(v)
    except Exception: return None

lb = lb[lb.LBTESTCD.isin(["ALT", "AST", "BILI", "ALP", "CREAT", "HGB", "WBC", "PLAT", "GLUC"]) & lb.USUBJID.isin(ids) & lb.LBSTRESN.notna() & lb.LBDY.notna()]
labs = [{"subject": r.USUBJID, "test": r.LBTESTCD, "day": int(r.LBDY), "value": float(r.LBSTRESN), "lln": None if pd.isna(r.LBSTNRLO) else float(r.LBSTNRLO), "uln": None if pd.isna(r.LBSTNRHI) else float(r.LBSTNRHI), "unit": r.LBSTRESU, "visit": r.VISIT} for r in lb.itertuples()]
ae = ae[ae.USUBJID.isin(ids)]
events = [{"subject": r.USUBJID, "term": r.AETERM, "pt": r.AEDECOD, "soc": r.AEBODSYS, "start_day": f(getattr(r, "AESTDY", None)), "end_day": f(getattr(r, "AEENDY", None)), "severity": r.AESEV, "serious": r.AESER == "Y"} for r in ae.itertuples()]
vs = vs[vs.VSTESTCD.isin(["WEIGHT", "HEIGHT", "SYSBP", "DIABP", "PULSE", "TEMP"]) & vs.USUBJID.isin(ids) & vs.VSSTRESN.notna() & vs.VSDY.notna()]
vitals = [{"subject": r.USUBJID, "test": r.VSTESTCD, "day": int(r.VSDY), "value": float(r.VSSTRESN), "unit": r.VSSTRESU, "visit": r.VISIT} for r in vs.itertuples()]
cm = cm[cm.USUBJID.isin(ids)]
meds = [{"subject": r.USUBJID, "name": str(r.CMTRT).title(), "dose": None if pd.isna(getattr(r, "CMDOSE", float("nan"))) else float(r.CMDOSE), "dose_unit": getattr(r, "CMDOSU", None) or None,
         "frequency": getattr(r, "CMDOSFRQ", None) or None, "route": getattr(r, "CMROUTE", None) or None, "indication": getattr(r, "CMINDC", None) or None,
         "start_day": f(getattr(r, "CMSTDY", None)), "end_day": f(getattr(r, "CMENDY", None))} for r in cm.itertuples()]
sites = sorted({s["site"] for s in subjects})
trial = {"id": "CDISCPILOT01", "name": "Safety and Efficacy of the Xanomeline Transdermal Therapeutic System in Patients with Mild to Moderate Alzheimer's Disease",
         "product": "Study drug (blinded)", "phase": "2", "sites": sites, "source": "CDISC SDTM/ADaM pilot project, educational use; treatment arm removed"}
with open(out, "w") as f:
    json.dump({"trial": trial, "subjects": subjects, "labs": labs, "events": events, "vitals": vitals, "medications": meds}, f)
print(f"subjects {len(subjects)} labs {len(labs)} events {len(events)} vitals {len(vitals)} medications {len(meds)} -> {out}")
