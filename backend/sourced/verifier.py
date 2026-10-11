"""Independent second pass over a filled form. Deterministic checks always run; a model second opinion runs when a key exists.
Verdicts per field: agree | single_source | disagree | rule_fail | missing | empty."""
from __future__ import annotations

from datetime import date

from .concepts import CONCEPTS, in_range, numbers_agree, parse_number
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


def verify(inst: FormInstance, form_def, llm=None) -> FormInstance:
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
            if disagree and not agree:
                verdict = "disagree"
            elif disagree and agree:
                verdict = "disagree"
            else:
                verdict = "agree"
            checks.append({"check": "cross_source", "ok": not disagree, "detail": {"agree": [{"value": a["value"], "source": a["receipt"]["source_org"], "days": a["days_from_visit"]} for a in agree],
                                                                                     "disagree": [{"value": a["value"], "source": a["receipt"]["source_org"], "days": a["days_from_visit"]} for a in disagree]}})
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
        field.verifier = {"verdict": verdict, "checks": checks, "method": method}
        flagged += verdict in ("disagree", "rule_fail", "missing")
    inst.n_flagged = flagged
    return inst
