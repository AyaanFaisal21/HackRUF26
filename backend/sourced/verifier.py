"""Independent second pass over a filled form. Deterministic checks always run; a model second opinion runs when a key exists.
Verdicts per field: agree | single_source | disagree | rule_fail | missing | empty."""
from __future__ import annotations

from datetime import date

from datetime import timedelta

from .concepts import CONCEPTS, convert, in_range, numbers_agree, parse_number
from .schema import FormInstance


def _d(v):
    if v is None:
        return None
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def _quote_matches(field, fact_attrs: dict, quote: str | None, concept: str) -> bool | None:
    """Does the number inside the quote match what the reader claimed it wrote down? Catches transcription slips."""
    if not quote or field.vtype != "number":
        return None
    written = parse_number(fact_attrs.get("as_written")) if fact_attrs else None
    if written is None:
        return None
    nums = [parse_number(tok) for tok in quote.replace("/", " ").split()]
    nums = [n for n in nums if n is not None]
    return any(abs(n - written) < 1e-6 for n in nums) if nums else None


def _said(rc: dict, value, unit: str | None) -> str:
    from .forms import tidy, where
    quote = f', "{tidy(rc["quote"])}"' if rc.get("quote") else ""
    return f"{rc['source_org']} ({where(rc)}{quote}) has {value} {unit or ''} on {str(rc.get('observed_at'))[:10]}".replace("  ", " ")


def _explain_scalar(field, disagree: list[dict]) -> str:
    """Plain-language account of a cross-source disagreement, built only from the receipts. No model."""
    parts = [_said(field.receipt or {}, field.value, field.unit)] + [_said(a["receipt"], a["value"], field.unit) for a in disagree]
    return "; ".join(parts) + ". These were measured within three days of each other, so they should agree and do not. The filled value is the one nearest the visit; the coordinator picks which source to trust."


_UNIT_CANDIDATES = {"kg": ["lb"], "cm": ["in"], "Cel": ["degF"], "umol/L": ["mg/dL"], "mmol/L": ["mg/dL"]}


def _transposed(a: float, b: float) -> bool:
    if abs(a - round(a)) > 1e-9 or abs(b - round(b)) > 1e-9:
        return False
    x, y = str(int(round(a))), str(int(round(b)))
    return len(x) == len(y) and x != y and sorted(x) == sorted(y) and sum(c != d for c, d in zip(x, y, strict=True)) == 2


def _history(store, patient_id: str, fd, visit_date, exclude: set) -> dict | None:
    """The patient's own values for this concept within two years, in the form's unit, excluding the values in dispute.
    One other reading is weak evidence and the wording says so; three or more is a pattern."""
    if store is None or not hasattr(store, "facts"):
        return None
    vals = []
    for f in store.facts(patient_id, fd.concept, visit_date - timedelta(days=730), visit_date + timedelta(days=730)):
        if f["id"] in exclude or f.get("value_num") is None:
            continue
        x = f["value_num"]
        if f.get("unit") != fd.unit:
            x = convert(x, f.get("unit"), fd.unit, fd.concept)
        if x is not None:
            vals.append(float(x))
    if not vals:
        return None
    vals.sort()
    return {"n": len(vals), "median": vals[len(vals) // 2], "lo": vals[0], "hi": vals[-1]}


def _near_history(fd, x: float, h: dict) -> bool:
    c = CONCEPTS[fd.concept]
    band = max(3 * c.get("tol", 0), 2 * c.get("rtol", 0) * h["median"], 0.08 * h["median"])
    return abs(x - h["median"]) <= band


def diagnose_scalar(field, fd, disagree: list[dict], store=None, patient_id: str | None = None, visit_date=None) -> dict | None:
    """Likely cause of a numeric disagreement. Unit arithmetic first, then digit patterns, then the patient's own history.
    A hypothesis with evidence for the coordinator, never an action."""
    v = float(field.value); r = field.receipt or {}; a = disagree[0]; av = float(a["value"]); ar = a["receipt"]
    ev = []
    for u in _UNIT_CANDIDATES.get(fd.unit or "", []):
        cv = convert(av, u, fd.unit, fd.concept)
        if cv is not None and numbers_agree(fd.concept, v, cv):
            ev.append(f"{av:g} read as {u} is {cv:.1f} {fd.unit}, which matches {ar['source_org']}'s value against {r.get('source_org')}'s {v:g}")
            return {"likely_cause": f"A unit label error: {ar['source_org']}'s {av:g} is {fd.unit} on paper but equals {v:g} {fd.unit} if it was written in {u}.",
                    "confidence": "likely", "evidence": ev, "verify_with": f"the {ar['source_org']} document",
                    "suggestion": {"action": "accept", "reason": f"{ar['source_org']}'s {av:g} matches {v:g} {fd.unit} when read as {u}; unit label error in the source"}}
        cv2 = convert(v, u, fd.unit, fd.concept)
        if cv2 is not None and numbers_agree(fd.concept, av, cv2):
            ev.append(f"{v:g} read as {u} is {cv2:.1f} {fd.unit}, which matches {ar['source_org']}'s {av:g}")
            return {"likely_cause": f"A unit label error: {r.get('source_org')}'s {v:g} equals {av:g} {fd.unit} if it was written in {u}.",
                    "confidence": "likely", "evidence": ev, "verify_with": f"the {r.get('source_org')} record",
                    "suggestion": {"action": "choose", "fact_id": ar.get("id"), "value": av, "reason": f"{r.get('source_org')}'s {v:g} matches {av:g} {fd.unit} when read as {u}; unit label error, took {ar['source_org']}"}}
    if _transposed(v, av):
        ev.append(f"{v:g} and {av:g} are the same digits in a different order")
        pattern = "Digits transposed in one source."
    elif min(v, av) > 0 and abs(max(v, av) / min(v, av) - 10) < 0.2:
        ev.append(f"{v:g} and {av:g} differ by a factor of ten")
        pattern = "A decimal point slipped in one source."
    else:
        pattern = None
    h = _history(store, patient_id, fd, visit_date, {r.get("id"), ar.get("id")}) if store is not None and patient_id and visit_date else None
    if h:
        ours, theirs = _near_history(fd, v, h), _near_history(fd, av, h)
        span = (f"{h['n']} other readings in the two years around the visit, median {h['median']:g} {fd.unit} (range {h['lo']:g} to {h['hi']:g})" if h["n"] > 1
                else f"only one other reading in the two years around the visit, {h['median']:g} {fd.unit}")
        if ours and not theirs:
            ev.append(f"{v:g} fits the patient's own history: {span}; {av:g} does not")
            return {"likely_cause": (pattern + " " if pattern else "") + f"{ar['source_org']}'s {av:g} is out of line with this patient's other readings; {r.get('source_org')}'s {v:g} fits them.",
                    "confidence": "possible", "evidence": ev, "verify_with": f"the {ar['source_org']} source document, then the patient if it stands",
                    "suggestion": {"action": "accept", "reason": f"{v:g} {fd.unit} fits the patient's history (median {h['median']:g} over {h['n']} readings); {ar['source_org']}'s {av:g} does not"}}
        if theirs and not ours:
            ev.append(f"{av:g} fits the patient's own history: {span}; {v:g} does not")
            return {"likely_cause": (pattern + " " if pattern else "") + f"{r.get('source_org')}'s {v:g} is out of line with this patient's other readings; {ar['source_org']}'s {av:g} fits them.",
                    "confidence": "possible", "evidence": ev, "verify_with": f"the {r.get('source_org')} record, then the patient if it stands",
                    "suggestion": {"action": "choose", "fact_id": ar.get("id"), "value": av, "reason": f"{av:g} {fd.unit} fits the patient's history (median {h['median']:g} over {h['n']} readings); {r.get('source_org')}'s {v:g} does not"}}
        ev.append(f"both values are within the patient's usual range: {span}")
    if pattern:
        return {"likely_cause": pattern + " The history does not say which.", "confidence": "possible", "evidence": ev, "verify_with": "both source documents", "suggestion": None}
    ev.append("no unit, digit, or history pattern separates the two values")
    return {"likely_cause": "Two real measurements that differ, or an error the receipts cannot locate.", "confidence": "unclear", "evidence": ev,
            "verify_with": "the measuring site, or re-measure at the next visit", "suggestion": None}


def verify(inst: FormInstance, form_def, llm=None, store=None) -> FormInstance:
    fdefs = {f.key: f for f in form_def.fields}
    flagged = 0
    for field in inst.fields:
        fd = fdefs[field.key]
        checks = []
        if field.vtype == "list":
            conflicts = [r for r in (field.rows or []) if r.get("conflicts")]
            multi = [r for r in (field.rows or []) if r.get("n_sources", 0) > 1]
            if not field.rows:
                verdict = "missing" if fd.required else "empty"
            elif conflicts:
                verdict = "disagree"
                checks.append({"check": "cross_source", "ok": False, "detail": [{"term": r["term"], "conflicts": r["conflicts"]} for r in conflicts]})
            elif multi:
                verdict = "agree"; checks.append({"check": "cross_source", "ok": True, "detail": f"{len(multi)} rows confirmed by more than one source"})
            else:
                verdict = "single_source"
            field.verifier = {"verdict": verdict, "checks": checks, "method": "rules"}
            flagged += verdict in ("disagree", "rule_fail", "missing")
            continue
        if field.value is None:
            verdict = "missing" if fd.required else "empty"
            field.verifier = {"verdict": verdict, "checks": [], "method": "rules"}
            flagged += verdict == "missing"
            continue
        verdict = "single_source"
        field_explanation = None
        field_diagnosis = None
        if field.vtype == "number":
            ok = in_range(fd.concept, float(field.value))
            checks.append({"check": "plausible_range", "ok": ok, "detail": f"{field.value} {field.unit} within {CONCEPTS[fd.concept].get('range')}"})
            if not ok:
                verdict = "rule_fail"
            qm = _quote_matches(field, (field.receipt or {}).get("attrs") or {}, (field.receipt or {}).get("quote"), fd.concept)
            if qm is not None:
                checks.append({"check": "quote_reparse", "ok": qm, "detail": "number in the quoted text matches the extracted value" if qm else "number in the quoted text does not match the extracted value"})
                if not qm:
                    verdict = "rule_fail"
        # only values measured within 3 days of the chosen one are comparable; a weight from last spring is history, not a conflict
        chosen_when = _d((field.receipt or {}).get("observed_at"))
        others = [a for a in field.alternatives if a["receipt"]["source_org"] != (field.receipt or {}).get("source_org")
                  and chosen_when and _d(a["receipt"].get("observed_at")) and abs((_d(a["receipt"]["observed_at"]) - chosen_when).days) <= 3]
        if others and verdict != "rule_fail":
            agree, disagree = [], []
            for a in others:
                same = numbers_agree(fd.concept, float(field.value), float(a["value"])) if field.vtype == "number" else str(a["value"]).strip().lower() == str(field.value).strip().lower()
                (agree if same else disagree).append(a)
            verdict = "disagree" if disagree else "agree"
            checks.append({"check": "cross_source", "ok": not disagree, "detail": {"agree": [{"value": a["value"], "source": a["receipt"]["source_org"], "days": a["days_from_visit"]} for a in agree],
                                                                                     "disagree": [{"value": a["value"], "source": a["receipt"]["source_org"], "days": a["days_from_visit"]} for a in disagree]}})
            if disagree:
                field_explanation = _explain_scalar(field, disagree)
                if field.vtype == "number":
                    try:
                        field_diagnosis = diagnose_scalar(field, fd, disagree, store, inst.patient_id, inst.visit_date)
                    except Exception as e:  # a diagnosis must never break the review
                        field_diagnosis = {"likely_cause": f"diagnosis skipped: {e.__class__.__name__}", "confidence": "unclear", "evidence": [], "suggestion": None, "verify_with": ""}
        elif not others and field.alternatives and verdict != "rule_fail":
            same_src = [a for a in field.alternatives]
            diff = [a for a in same_src if field.vtype == "number" and not numbers_agree(fd.concept, float(field.value), float(a["value"]))]
            checks.append({"check": "same_source_history", "ok": True, "detail": f"{len(same_src)} other value(s) from the same source in the window" + (", nearest chosen" if diff else "")})
        method = "rules"
        if llm is not None and field.receipt and field.receipt.get("quote") and verdict in ("single_source", "disagree"):
            try:
                from .schema import DocFact
                second = llm.parse("Extract exactly one value for the named concept from the quoted text. Copy it as written.",
                                   f"Concept: {fd.label}. Text: {field.receipt['quote']}", DocFact)
                n = parse_number(second.value)
                written = parse_number(((field.receipt or {}).get("attrs") or {}).get("as_written"))
                ok = (n is not None and written is not None and abs(n - written) < 1e-6)
                checks.append({"check": "model_second_opinion", "ok": ok, "detail": f"second reading: {second.value} {second.unit or ''}".strip()})
                method = "rules+model"
                if not ok:
                    verdict = "rule_fail"
            except Exception as e:  # the second opinion must never break the review
                checks.append({"check": "model_second_opinion", "ok": None, "detail": f"skipped: {e.__class__.__name__}"})
        field.verifier = {"verdict": verdict, "checks": checks, "method": method, **({"explanation": field_explanation} if field_explanation else {}), **({"diagnosis": field_diagnosis} if field_diagnosis else {})}
        flagged += verdict in ("disagree", "rule_fail", "missing")
    inst.n_flagged = flagged
    return inst
