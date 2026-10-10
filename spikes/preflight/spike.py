"""Pre-Flight spike: can we get the Schedule of Activities out of real protocol PDFs, and join endpoints to it?"""
import re, json, sys, glob, pdfplumber
from collections import Counter

SOA_KW = re.compile(r"schedule of (activities|assessments|events)|time and events schedule|study schedule", re.I)
WEEK = re.compile(r"\b(?:Week|Wk|W)\s?(\d{1,3})\b", re.I)
ENDPOINT_CTX = re.compile(r"(primary|secondary|key secondary)\s+(objective|endpoint|outcome)s?", re.I)

report = {}
for pdf_path in sorted(glob.glob("data/*.pdf")):
    name = pdf_path.split("/")[-1]
    with pdfplumber.open(pdf_path) as pdf:
        n = len(pdf.pages)
        texts = []
        for p in pdf.pages:
            try: texts.append(p.extract_text() or "")
            except Exception as e: texts.append("")
        # 1. locate SoA pages: keyword hit AND many week tokens AND wide/landscape or many 'X' cells
        cand = []
        for i, t in enumerate(texts):
            weeks = len(WEEK.findall(t)); xs = len(re.findall(r"(?<![A-Za-z])X(?![A-Za-z])", t))
            if (SOA_KW.search(t) and weeks >= 4) or (weeks >= 8 and xs >= 15):
                cand.append((i+1, weeks, xs))
        # 2. try table extraction on the top candidate pages
        tables = []
        for pg, w, x in cand[:6]:
            page = pdf.pages[pg-1]
            for strat in ({"vertical_strategy":"lines","horizontal_strategy":"lines"}, {"vertical_strategy":"text","horizontal_strategy":"text"}):
                try: tb = page.extract_tables(table_settings=strat)
                except Exception: tb = []
                good = [t for t in tb if t and len(t) >= 5 and max(len(r) for r in t) >= 5]
                if good:
                    t0 = max(good, key=lambda t: len(t)*max(len(r) for r in t))
                    hdr = [c for c in (t0[0] + (t0[1] if len(t0)>1 else [])) if c]
                    wk_cols = sorted({int(m) for h in hdr for m in WEEK.findall(h)})
                    tables.append({"page": pg, "strategy": strat["vertical_strategy"], "rows": len(t0), "cols": max(len(r) for r in t0), "week_columns": wk_cols, "first_col_sample": [r[0] for r in t0[1:8] if r and r[0]]})
                    break
        # 3. endpoint timepoints from objectives/endpoints sections
        ep_weeks = Counter()
        for t in texts[:40]:
            for m in ENDPOINT_CTX.finditer(t):
                window = t[m.start(): m.start()+1500]
                for w in WEEK.findall(window): ep_weeks[int(w)] += 1
        soa_weeks = sorted({w for tb in tables for w in tb["week_columns"]})
        joinable = {w: (w in soa_weeks) for w in sorted(ep_weeks)}
        report[name] = {"pages": n, "soa_candidate_pages": cand[:8], "tables": tables, "endpoint_weeks_mentioned": dict(sorted(ep_weeks.items())), "soa_week_columns": soa_weeks, "endpoint_week_in_soa": joinable}
        print(f"\n=== {name}  ({n} pages)")
        print(" SoA candidate pages (page, week tokens, X cells):", cand[:8])
        for tb in tables: print("  table p%(page)s via %(strategy)s: %(rows)dx%(cols)d  week cols=%(week_columns)s  rows: %(first_col_sample)s" % tb)
        print(" endpoint weeks mentioned:", dict(sorted(ep_weeks.items())))
        print(" endpoint week -> found as SoA column:", joinable)
json.dump(report, open("data/soa_report.json","w"), indent=1)
