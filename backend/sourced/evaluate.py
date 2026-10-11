"""Score the system against the answer key: fill rate, accuracy, receipt coverage, planted-trap handling, false alarms."""
from __future__ import annotations

from datetime import date

from .concepts import numbers_agree
from .forms import FORMS, fill
from .verifier import verify


def evaluate(store, truth: dict, patients: list[dict], max_patients: int = 60, llm=None) -> dict:
    planted = truth["planted"]
    planted_by = {}
    for p in planted:
        planted_by.setdefault((p["patient_id"], p["visit"], p["concept"]), []).append(p)
    doc_patients = sorted({p["patient_id"] for p in planted if p["patient_id"].startswith("01-")})[:max_patients]
    n_fields = n_filled = n_correct = n_receipt = n_flag = n_false_alarm = 0
    per_concept: dict[str, dict] = {}
    conflicts_caught = conflicts_total = traps_ok = traps_total = gaps_filled = gaps_total = 0
    for pid in doc_patients:
        vt = truth["visit_truth"].get(pid, {})
        visits = sorted({p["visit"] for p in planted if p["patient_id"] == pid and p["concept"] != "medication"})
        for v in visits:
            vd = date.fromisoformat(v)
            for form_id in ("vs_visit", "lb_visit"):
                inst = verify(fill(store, pid, FORMS[form_id], vd), FORMS[form_id], llm)
                for f in inst.fields:
                    tv = vt.get(v, {}).get(f.key)
                    if tv is None:
                        continue
                    n_fields += 1
                    pc = per_concept.setdefault(f.key, {"n": 0, "filled": 0, "correct": 0})
                    pc["n"] += 1
                    if f.value is None:
                        continue
                    n_filled += 1; pc["filled"] += 1
                    n_receipt += bool(f.receipt and (f.receipt.get("quote") or f.receipt.get("resource_ref")))
                    ok = numbers_agree(f.key, float(f.value), float(tv))
                    n_correct += ok; pc["correct"] += ok
                    verdict = (f.verifier or {}).get("verdict")
                    key = (pid, v, f.key)
                    kinds = {p["kind"] for p in planted_by.get(key, [])}
                    if "conflict" in kinds:
                        conflicts_total += 1; conflicts_caught += verdict in ("disagree", "rule_fail")
                    elif verdict in ("disagree", "rule_fail"):
                        n_false_alarm += 1
                    if "unit_trap" in kinds:
                        traps_total += 1; traps_ok += ok
                    if "gap_fill" in kinds:
                        gaps_total += 1; gaps_filled += f.value is not None and (f.receipt or {}).get("document_id") is not None
                    n_flag += verdict in ("disagree", "rule_fail")
    # children: the school form must union immunizations across both clinics
    kids_ok = kids_total = 0
    for c in truth.get("children", []):
        inst = fill(store, c["patient_id"], FORMS["nj_ch14"], date.today())
        imm = next(f for f in inst.fields if f.key == "immunizations")
        kids_total += 1; kids_ok += len(imm.rows or []) == c["immunizations_total"]
    return {"patients_scored": len(doc_patients), "fields_with_truth": n_fields, "fill_rate": round(n_filled / n_fields, 3) if n_fields else None,
            "accuracy_of_filled": round(n_correct / n_filled, 3) if n_filled else None, "receipt_coverage": round(n_receipt / n_filled, 3) if n_filled else None,
            "planted_conflicts": {"total": conflicts_total, "caught": conflicts_caught, "catch_rate": round(conflicts_caught / conflicts_total, 3) if conflicts_total else None},
            "unit_traps": {"total": traps_total, "converted_correctly": traps_ok}, "gap_fills": {"total": gaps_total, "filled_from_document": gaps_filled},
            "false_alarms": n_false_alarm, "fields_flagged": n_flag, "children_immunizations_complete": f"{kids_ok}/{kids_total}",
            "per_concept": {k: {**v, "accuracy": round(v["correct"] / v["filled"], 3) if v["filled"] else None} for k, v in sorted(per_concept.items())}}


def to_markdown(m: dict, reader: str) -> str:
    lines = [f"## Evaluation (reader: {reader})", "", f"Patients scored: {m['patients_scored']}. Fields with a known truth: {m['fields_with_truth']}.", "",
             "| Metric | Value |", "|---|---|",
             f"| Fields filled automatically | {m['fill_rate']:.1%} |", f"| Accuracy of filled fields | {m['accuracy_of_filled']:.1%} |", f"| Filled fields with a receipt | {m['receipt_coverage']:.1%} |",
             f"| Planted conflicts caught by the verifier | {m['planted_conflicts']['caught']}/{m['planted_conflicts']['total']} |",
             f"| Unit traps converted correctly | {m['unit_traps']['converted_correctly']}/{m['unit_traps']['total']} |",
             f"| Gaps filled from an outside document | {m['gap_fills']['filled_from_document']}/{m['gap_fills']['total']} |",
             f"| False alarms (flagged, no planted conflict) | {m['false_alarms']} |", f"| School forms with complete immunizations across clinics | {m['children_immunizations_complete']} |", "",
             "| Concept | Fields | Filled | Accuracy |", "|---|---|---|---|"]
    lines += [f"| {k} | {v['n']} | {v['filled']} | {v['accuracy']:.1%} |" if v["accuracy"] is not None else f"| {k} | {v['n']} | {v['filled']} | - |" for k, v in m["per_concept"].items()]
    if reader == "oracle":
        lines += ["", "Oracle mode uses the answer key as the document reader, so document facts are extracted perfectly by construction. It validates coding, unit conversion, the filler, and the verifier. Run with --reader model for real reading numbers."]
    return "\n".join(lines)
