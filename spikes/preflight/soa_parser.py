"""Coordinate-based Schedule of Activities parser: snap each X mark to the nearest visit/week column by x-position."""
import pdfplumber, re, json, sys

INT = re.compile(r"^-?\d{1,3}$")

def find_header_rows(words, label_regex):
    """Return (y, [(x_center, token)]) for the row whose text starts with label_regex (e.g. 'Week')."""
    rows = {}
    for w in words:
        rows.setdefault(round(w["top"]), []).append(w)
    for y, ws in sorted(rows.items()):
        ws.sort(key=lambda w: w["x0"])
        line = " ".join(w["text"] for w in ws)
        if re.match(label_regex, line, re.I):
            nums = [((w["x0"]+w["x1"])/2, w["text"]) for w in ws if INT.match(w["text"].replace("±",""))]
            if len(nums) >= 4:
                return y, nums, line
    return None, [], ""

def parse_soa_page(page):
    words = page.extract_words(keep_blank_chars=False, use_text_flow=False, x_tolerance=1.5)
    vy, visits, vline = find_header_rows(words, r"^Visit\b")
    wy, weeks, wline = find_header_rows(words, r"^Week")
    if not weeks and not visits: return None
    cols = weeks or visits
    header_y = max(vy or 0, wy or 0)
    # activity rows: any line below the header whose first token is alphabetic and that contains X marks
    rows = {}
    for w in words:
        if w["top"] <= header_y + 2: continue
        rows.setdefault(round(w["top"]/3), []).append(w)   # 3pt bucketing merges superscript footnote letters
    out = []
    xcols = [c[0] for c in cols]
    for _, ws in sorted(rows.items()):
        ws.sort(key=lambda w: w["x0"])
        label = " ".join(w["text"] for w in ws if not re.fullmatch(r"X[a-z]{0,2}", w["text"]) and w["x0"] < xcols[0]-10)
        marks = [w for w in ws if re.fullmatch(r"X[a-z]{0,2}", w["text"])]
        if not label or not marks: continue
        hit = set()
        for m in marks:
            xc = (m["x0"]+m["x1"])/2
            j = min(range(len(xcols)), key=lambda k: abs(xcols[k]-xc))
            if abs(xcols[j]-xc) < 18: hit.add(cols[j][1])
        out.append({"activity": label, "at": sorted(hit, key=lambda s: int(s.replace("±","") or 0))})
    return {"visit_row": vline[:120], "week_row": wline[:120], "columns": [c[1] for c in cols], "activities": out}

if __name__ == "__main__":
    targets = {"dulaglutide_NCT03495102.pdf": [13,14,15], "tirzepatide_NCT03131687.pdf": [12,13,14,15], "canagliflozin_NCT02065791.pdf": [26,27,28]}
    result = {}
    for name, pages in targets.items():
        with pdfplumber.open("data/"+name) as pdf:
            acts = []; cols = None; hdr = None
            for pg in pages:
                r = parse_soa_page(pdf.pages[pg-1])
                if r:
                    cols = cols or r["columns"]; hdr = hdr or (r["visit_row"], r["week_row"]); acts += r["activities"]
            result[name] = {"columns": cols, "header": hdr, "n_activities": len(acts), "activities": acts}
            print(f"\n=== {name}: columns={cols}\n    header={hdr}\n    {len(acts)} activity rows parsed")
            for a in acts[:14]: print("     ", a["activity"][:48].ljust(48), a["at"])
            for key in ("HbA1c","Weight","Vital","Electrocardiogram","ECG","eGFR","Blood pressure"):
                m = [a for a in acts if key.lower() in a["activity"].lower()]
                if m: print("   >>", key, "->", m[0]["at"])
    json.dump(result, open("data/soa_parsed.json","w"), indent=1)
