"""Hidden in the Labs spike: Hy's Law flags, CTCAE grading, eDISH plot, planted signals, blinding."""
import pandas as pd, numpy as np, json, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt

lb = pd.read_sas("data/lb.xpt", format="xport", encoding="latin1")
dm = pd.read_sas("data/dm.xpt", format="xport", encoding="latin1")
ae = pd.read_sas("data/ae.xpt", format="xport", encoding="latin1")
# BLINDING: arm lives in a separate locked file; the analysis never joins it.
dm[["USUBJID","ARM"]].to_csv("data/UNBLINDED_arm_lookup.csv", index=False)
dm_b = dm[dm.ARM != "Screen Failure"][["USUBJID","SITEID","AGE","SEX"]]

liv = lb[lb.LBTESTCD.isin(["ALT","AST","BILI","ALP"]) & lb.USUBJID.isin(dm_b.USUBJID)].copy()
liv["xULN"] = liv.LBSTRESN / liv.LBSTNRHI
post = liv[liv.LBDY > 1]  # post-baseline only

def ctcae_grade(test, x):
    # CTCAE v5: ALT/AST G1 >ULN-3x, G2 >3-5x, G3 >5-20x, G4 >20x ; bilirubin G1 >ULN-1.5x, G2 >1.5-3x, G3 >3-10x, G4 >10x
    if pd.isna(x) or x <= 1: return 0
    cuts = (1.5,3,10) if test == "BILI" else (3,5,20)
    return 1 + sum(x > c for c in cuts)
post["grade"] = [ctcae_grade(t,x) for t,x in zip(post.LBTESTCD, post.xULN)]

def hys_law(df):
    """Hy's Law candidate: peak ALT or AST >= 3x ULN AND peak bilirubin >= 2x ULN (FDA DILI guidance 2009). ALP < 2x ULN supports hepatocellular pattern."""
    peaks = df.pivot_table(index="USUBJID", columns="LBTESTCD", values="xULN", aggfunc="max")
    peaks["hys_law"] = ((peaks[["ALT","AST"]].max(axis=1) >= 3) & (peaks["BILI"] >= 2))
    peaks["temple_corollary"] = peaks[["ALT","AST"]].max(axis=1) >= 3   # 3x ULN on its own = watch list
    return peaks

peaks = hys_law(post)
print("subjects analysed:", peaks.shape[0])
print("natural Hy's Law candidates:", int(peaks.hys_law.sum()), " | ALT/AST >=3x ULN:", int(peaks.temple_corollary.sum()))
print("CTCAE grade distribution (post-baseline liver rows):", post.grade.value_counts().sort_index().to_dict())
print("max xULN seen: ALT %.2f AST %.2f BILI %.2f" % (peaks.ALT.max(), peaks.AST.max(), peaks.BILI.max()))

# ---- plant signals with an answer key (the pilot data is too clean to demo on)
rng = np.random.default_rng(3)
planted = {}
plant_subjects = rng.choice(peaks.index, 3, replace=False)
sim = post.copy()
for i, s in enumerate(plant_subjects):
    rows = sim[(sim.USUBJID == s)]
    vis = sorted(rows.LBDY.unique())[3:6]  # three consecutive visits mid-study
    for t, mult in (("ALT", (4.2, 6.5, 3.8)), ("AST", (3.5, 5.1, 3.0)), ("BILI", (1.4, 2.6, 2.1))):
        for d, m in zip(vis, mult):
            idx = sim[(sim.USUBJID == s) & (sim.LBTESTCD == t) & (sim.LBDY == d)].index
            sim.loc[idx, "xULN"] = m; sim.loc[idx, "LBSTRESN"] = m * sim.loc[idx, "LBSTNRHI"]
    planted[s] = {"type": "hys_law", "days": [int(d) for d in vis]}
# site-level slow creep in ALT at one site
creep_site = dm_b.SITEID.value_counts().index[2]
creep_subj = dm_b[dm_b.SITEID == creep_site].USUBJID
m = sim.USUBJID.isin(creep_subj) & (sim.LBTESTCD == "ALT")
sim.loc[m, "xULN"] = sim.loc[m, "xULN"] * (1 + 0.012 * sim.loc[m, "LBDY"])  # ~+100% by day 84... scaled per visit
planted[f"SITE-{creep_site}"] = {"type": "site_alt_creep", "n_subjects": int(len(creep_subj))}
sim["grade"] = [ctcae_grade(t,x) for t,x in zip(sim.LBTESTCD, sim.xULN)]

peaks2 = hys_law(sim)
found = set(peaks2[peaks2.hys_law].index)
print("\nplanted Hy's Law subjects:", list(plant_subjects))
print("detected:", sorted(found), " recall:", len(found & set(plant_subjects))/3, " false positives:", sorted(found - set(plant_subjects)))

# site creep detection: slope of mean ALT xULN vs study day, per site, vs other sites
sim2 = sim[sim.LBTESTCD == "ALT"].merge(dm_b[["USUBJID","SITEID"]], on="USUBJID")
slopes = {}
for site, g in sim2.groupby("SITEID"):
    if g.USUBJID.nunique() < 4: continue
    slopes[site] = np.polyfit(g.LBDY, g.xULN, 1)[0] * 100  # xULN change per 100 days
z = pd.Series(slopes); z = (z - z.median()) / (z.std() + 1e-9)
print("site ALT slope z-scores (top 3):", z.sort_values(ascending=False).head(3).round(2).to_dict(), " planted site:", creep_site)

# ---- evidence-bearing flags (what the UI shows)
flags = []
for s in found:
    r = sim[(sim.USUBJID == s) & (sim.LBTESTCD.isin(["ALT","AST","BILI"])) & (sim.xULN >= 2)].sort_values("LBDY")
    flags.append({"subject": s, "flag": "Hy's Law candidate", "rule": "FDA DILI guidance 2009: ALT/AST >=3x ULN with TBL >=2x ULN",
                  "evidence": [{"test": t, "day": int(d), "visit": v, "value": round(float(val),1), "uln": float(u), "xULN": round(float(x),2)} for t,d,v,val,u,x in zip(r.LBTESTCD, r.LBDY, r.VISIT, r.LBSTRESN, r.LBSTNRHI, r.xULN)],
                  "concurrent_AEs": ae[(ae.USUBJID == s)].AEDECOD.head(5).tolist()})
json.dump({"flags": flags, "answer_key": {str(k): v for k,v in planted.items()}}, open("data/flags.json","w"), indent=1, default=str)

# ---- eDISH plot: peak ALT xULN vs peak bilirubin xULN, log-log, Hy's Law quadrant
fig, ax = plt.subplots(figsize=(6,5))
ax.scatter(peaks2.ALT, peaks2.BILI, s=14, alpha=.6, label="subject")
hl = peaks2[peaks2.hys_law]; ax.scatter(hl.ALT, hl.BILI, s=40, color="red", label="Hy's Law quadrant")
ax.axvline(3, ls="--", c="gray"); ax.axhline(2, ls="--", c="gray")
ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xlabel("peak ALT (x ULN)"); ax.set_ylabel("peak total bilirubin (x ULN)")
ax.set_title("eDISH (blinded) - CDISC pilot + 3 planted signals"); ax.legend(); fig.tight_layout(); fig.savefig("data/edish.png", dpi=130)
print("\nwrote data/flags.json, data/edish.png;  arm labels isolated in data/UNBLINDED_arm_lookup.csv")
