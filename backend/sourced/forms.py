"""Form definitions and the filler. A form is a list of questions; the filler answers each from the ledger with a receipt."""
from __future__ import annotations

import re
import time
from datetime import date, timedelta

from .concepts import CONCEPTS, convert
from .schema import FieldDef, FilledField, FormDef, FormInstance

VISIT = dict(window_before=3, window_after=1)
F = FieldDef
FORM_DEFS: list[FormDef] = [
    FormDef(id="vs_visit", name="Vital Signs", domain="CDASH VS", description="Vital signs recorded at the visit.", fields=[
        F(key="sbp", label="Systolic BP", concept="sbp", vtype="number", unit="mmHg", **VISIT), F(key="dbp", label="Diastolic BP", concept="dbp", vtype="number", unit="mmHg", **VISIT),
        F(key="hr", label="Heart rate", concept="hr", vtype="number", unit="/min", **VISIT), F(key="temp", label="Temperature", concept="temp", vtype="number", unit="Cel", required=False, **VISIT),
        F(key="weight", label="Weight", concept="weight", vtype="number", unit="kg", **VISIT), F(key="height", label="Height", concept="height", vtype="number", unit="cm", window_before=400, window_after=1, required=False)]),
    FormDef(id="lb_visit", name="Laboratory Results", domain="CDASH LB", description="Chemistry and hematology collected for the visit.", fields=[
        F(key=k, label=CONCEPTS[k]["display"], concept=k, vtype="number", unit=CONCEPTS[k]["unit"], window_before=7, window_after=2, required=k not in ("glucose",))
        for k in ("alt", "ast", "bili", "alp", "creat", "hgb", "wbc", "plat", "glucose")]),
    FormDef(id="cm_log", name="Concomitant Medications", domain="CDASH CM", description="Medications the patient is taking at the visit.", fields=[
        F(key="medications", label="Medications", concept="medication", vtype="list", window_before=36500, window_after=0, columns=["name", "dose", "frequency", "route", "start", "end", "indication"])]),
    FormDef(id="ae_log", name="Adverse Events", domain="CDASH AE", description="Events that started since the previous visit.", fields=[
        F(key="events", label="Adverse events", concept="adverse_event", vtype="list", window_before=35, window_after=1, required=False, columns=["term", "start", "end", "severity", "serious"])]),
    FormDef(id="dm", name="Demographics", domain="CDASH DM", description="Demographics as recorded in source.", fields=[
        F(key="birth_date", label="Date of birth", concept="birth_date", vtype="date", window_before=36500, window_after=0), F(key="sex", label="Sex", concept="sex", vtype="text", window_before=36500, window_after=0),
        F(key="race", label="Race", concept="race", vtype="text", window_before=36500, window_after=0, required=False)]),
    FormDef(id="mh", name="Medical History", domain="CDASH MH", description="Conditions recorded before or at the visit.", fields=[
        F(key="conditions", label="Conditions", concept="condition", vtype="list", window_before=36500, window_after=0, required=False, columns=["term", "start", "end"])]),
    FormDef(id="nj_ch14", name="Universal Child Health Record", domain="NJ CH-14", description="New Jersey school and child care health form, provider section.", fields=[
        F(key="birth_date", label="Date of birth", concept="birth_date", vtype="date", window_before=36500, window_after=0), F(key="sex", label="Sex", concept="sex", vtype="text", window_before=36500, window_after=0),
        F(key="height", label="Height", concept="height", vtype="number", unit="cm", window_before=365, window_after=0), F(key="weight", label="Weight", concept="weight", vtype="number", unit="kg", window_before=365, window_after=0),
        F(key="sbp", label="Blood pressure, systolic", concept="sbp", vtype="number", unit="mmHg", window_before=365, window_after=0, required=False), F(key="dbp", label="Blood pressure, diastolic", concept="dbp", vtype="number", unit="mmHg", window_before=365, window_after=0, required=False),
        F(key="immunizations", label="Immunizations", concept="immunization", vtype="list", window_before=36500, window_after=0, columns=["vaccine", "date", "dose_number"]),
        F(key="allergies", label="Allergies", concept="allergy", vtype="list", window_before=36500, window_after=0, required=False, columns=["term", "reaction"]),
        F(key="conditions", label="Chronic conditions", concept="condition", vtype="list", window_before=36500, window_after=0, required=False, columns=["term", "start"]),
        F(key="medications", label="Medications", concept="medication", vtype="list", window_before=36500, window_after=0, required=False, columns=["name", "dose", "frequency"])]),
]
FORMS = {f.id: f for f in FORM_DEFS}


_DOSE = re.compile(r"(-?\d+(?:\.\d+)?)\s*([a-zA-Zµ/%]+)?")


def norm_cell(col: str, v) -> str | None:
    """Comparable form of a list-row cell. Doses compare by number and unit ('81.0 MG QD' == '81 mg'); dates by ISO day; text lowercased."""
    if v is None:
        return None
    s = str(v).strip()
    if col == "dose":
        m = _DOSE.search(s)
        if m:
            n = float(m.group(1)); u = (m.group(2) or "").lower().rstrip("s")
            return f"{n:g} {u}".strip()
        return s.lower()
    if col in ("start", "end", "date"):
        return s[:10]
    if col == "status":
        return "ended" if s.startswith("ended") else "active"
    return s.lower()


def receipt(fact: dict) -> dict:
    return {k: fact.get(k) for k in ("id", "source_org", "document_id", "page", "span_start", "span_end", "quote", "resource_ref", "extractor", "observed_at", "confidence", "unit", "attrs")}


def _row_key(fact: dict) -> str:
    key = (fact.get("value_text") or "").strip().lower()
    if fact.get("concept") in ("immunization", "adverse_event"):
        key += f"@{fact.get('observed_at')}"
    return key


def fill(store, patient_id: str, form: FormDef, visit_date: date) -> FormInstance:
    t0 = time.perf_counter()
    fields: list[FilledField] = []
    for fd in form.fields:
        start, end = visit_date - timedelta(days=fd.window_before), visit_date + timedelta(days=fd.window_after)
        facts = store.facts(patient_id, fd.concept, start, end)
        if fd.vtype == "list":
            rows: dict[str, dict] = {}
            for f in facts:
                if fd.concept == "medication":
                    e = f.get("end_at")
                    if e and e < visit_date - timedelta(days=90):
                        continue   # ended long before the visit
                k = _row_key(f)
                row = rows.setdefault(k, {"term": f.get("value_text"), "name": f.get("value_text"), "vaccine": f.get("value_text"), "sources": [], "values": {}})
                for col in fd.columns:
                    v = f.get("attrs", {}).get(col) if col not in ("term", "name", "vaccine", "date") else (f.get("observed_at") if col == "date" else row[col])
                    if col == "start" and not v:
                        v = f.get("attrs", {}).get("start") or (f.get("observed_at") if fd.concept != "medication" else None)
                    if col == "end" and not v:
                        v = f.get("end_at")
                    if col == "dose_number" and not v:
                        v = f.get("attrs", {}).get("dose_number")
                    row["values"].setdefault(col, []).append({"value": str(v) if v is not None else None, "source_org": f["source_org"], "fact_id": f["id"]})
                if fd.concept == "medication":
                    e = f.get("end_at")
                    status = f"ended {e}" if e and e <= visit_date else "active"
                    row["values"].setdefault("status", []).append({"value": status, "source_org": f["source_org"], "fact_id": f["id"]})
                row["sources"].append(receipt(f))
            out = []
            for row in rows.values():
                cells = {}
                for col, vals in row["values"].items():
                    by_norm = {}
                    for v in vals:
                        if v["value"] is not None:
                            by_norm.setdefault(norm_cell(col, v["value"]), v["value"])
                    cells[col] = sorted(by_norm.values())[0] if by_norm else None
                    if len(by_norm) > 1:
                        row.setdefault("conflicts", {})[col] = sorted(by_norm.values())
                out.append({**{c: cells.get(c) for c in fd.columns}, **({"status": cells.get("status")} if "status" in cells else {}), "term": row["term"], "sources": row["sources"], "conflicts": row.get("conflicts", {}), "n_sources": len({s["source_org"] for s in row["sources"]})})
            out.sort(key=lambda r: (r.get("start") or r.get("date") or "", r["term"] or ""))
            fields.append(FilledField(key=fd.key, label=fd.label, vtype="list", rows=out, confidence=1.0 if out else 0.0))
            continue
        # scalar: nearest to the visit, then most confident
        scored = []
        for f in facts:
            days = abs((f["observed_at"] - visit_date).days)
            value = f.get("value_num") if fd.vtype == "number" else f.get("value_text")
            if fd.vtype == "number" and value is not None and f.get("unit") != fd.unit:
                cv = convert(value, f.get("unit"), fd.unit, fd.concept)
                value = round(cv, 2) if cv is not None else value
            if value is None:
                continue
            scored.append((days, -f["confidence"], f, value))
        scored.sort(key=lambda x: (x[0], x[1]))
        if not scored:
            fields.append(FilledField(key=fd.key, label=fd.label, vtype=fd.vtype, unit=fd.unit, value=None, confidence=0.0))
            continue
        days, _, best, value = scored[0]
        conf = round(max(0.05, best["confidence"] * (1 - 0.03 * min(days, 20))), 2)
        alts = []
        for d2, _, f2, v2 in scored[1:]:
            if f2["id"] != best["id"]:
                alts.append({"value": v2, "days_from_visit": d2, "receipt": receipt(f2)})
        fields.append(FilledField(key=fd.key, label=fd.label, vtype=fd.vtype, unit=fd.unit, value=value, fact_id=best["id"], confidence=conf, receipt=receipt(best), alternatives=alts[:6]))
    inst = FormInstance(form_id=form.id, patient_id=patient_id, visit_date=visit_date, fields=fields, filled_ms=int((time.perf_counter() - t0) * 1000),
                        n_fields=len(fields), n_filled=sum(1 for f in fields if (f.value is not None) or f.rows))
    return inst
