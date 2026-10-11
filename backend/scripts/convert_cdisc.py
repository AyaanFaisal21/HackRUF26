"""One-time conversion of the CDISC SDTM pilot (XPT) into the compact JSON the app loads.
Drops the treatment arm entirely so nothing downstream can unblind. Needs pandas (system python is fine).
usage: python3 convert_cdisc.py <dir with dm/lb/ae/vs .xpt> <out.json>"""
import json, sys
import pandas as pd

src, out = sys.argv[1], sys.argv[2]
rd = lambda n: pd.read_sas(f"{src}/{n}.xpt", format="xport", encoding="latin1")
dm, lb, ae, vs = rd("dm"), rd("lb"), rd("ae"), rd("vs")
dm = dm[dm.ARM != "Screen Failure"]
subjects = [{"id": r.USUBJID, "site": str(r.SITEID), "age": int(r.AGE), "sex": r.SEX, "race": r.RACE} for r in dm.itertuples()]
ids = set(dm.USUBJID)
lb = lb[lb.LBTESTCD.isin(["ALT", "AST", "BILI", "ALP", "CREAT"]) & lb.USUBJID.isin(ids) & lb.LBSTRESN.notna() & lb.LBDY.notna()]
labs = [{"subject": r.USUBJID, "test": r.LBTESTCD, "day": int(r.LBDY), "value": float(r.LBSTRESN), "lln": float(r.LBSTNRLO), "uln": float(r.LBSTNRHI), "unit": r.LBSTRESU, "visit": r.VISIT} for r in lb.itertuples()]
ae = ae[ae.USUBJID.isin(ids)]
def f(v):
    try: return None if pd.isna(v) else int(v)
    except Exception: return None
events = [{"subject": r.USUBJID, "term": r.AETERM, "pt": r.AEDECOD, "soc": r.AEBODSYS, "start_day": f(getattr(r, "AESTDY", None)), "end_day": f(getattr(r, "AEENDY", None)), "severity": r.AESEV, "serious": r.AESER == "Y"} for r in ae.itertuples()]
vs = vs[vs.VSTESTCD.isin(["WEIGHT", "SYSBP", "DIABP"]) & vs.USUBJID.isin(ids) & vs.VSSTRESN.notna() & vs.VSDY.notna()]
vitals = [{"subject": r.USUBJID, "test": r.VSTESTCD, "day": int(r.VSDY), "value": float(r.VSSTRESN), "unit": r.VSSTRESU} for r in vs.itertuples()]
sites = sorted({s["site"] for s in subjects})
trial = {"id": "CDISCPILOT01", "name": "Safety and Efficacy of the Xanomeline Transdermal Therapeutic System in Patients with Mild to Moderate Alzheimer's Disease",
         "product": "Study drug (blinded)", "phase": "2", "sites": sites, "source": "CDISC SDTM/ADaM pilot project, educational use; treatment arm removed"}
json.dump({"trial": trial, "subjects": subjects, "labs": labs, "events": events, "vitals": vitals}, open(out, "w"))
print(f"subjects {len(subjects)} sites {len(sites)} labs {len(labs)} events {len(events)} vitals {len(vitals)} -> {out}")
