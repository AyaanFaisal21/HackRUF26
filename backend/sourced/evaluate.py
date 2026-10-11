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
    # medication dose conflicts: the medication log row for that drug must show the two doses
    for p in [p for p in planted if p["kind"] == "conflict" and p["concept"] == "medication" and p["patient_id"] in doc_patients]:
        inst = verify(fill(store, p["patient_id"], FORMS["cm_log"], date.fromisoformat(p["visit"])), FORMS["cm_log"])
        drug = p["doc_value"].split(" ")[0].lower()
        row = next((r for r in (inst.fields[0].rows or []) if drug in (r.get("term") or "").lower()), None)
        conflicts_total += 1; conflicts_caught += bool(row and (row.get("conflicts", {}).get("dose") or row.get("conflicts", {}).get("status")))
    # children: the school form must union immunizations across both clinics; the three planted weight conflicts must be flagged
    kids_ok = kids_total = 0
    kid_conflicts = {p["patient_id"] for p in planted if p["kind"] == "conflict" and p["patient_id"].startswith("PED")}
    for c in truth.get("children", []):
        inst = verify(fill(store, c["patient_id"], FORMS["nj_ch14"], date.today()), FORMS["nj_ch14"])
        imm = next(f for f in inst.fields if f.key == "immunizations")
        kids_total += 1; kids_ok += len(imm.rows or []) == c["immunizations_total"]
        if c["patient_id"] in kid_conflicts:
            w = next(f for f in inst.fields if f.key == "weight")
            conflicts_total += 1; conflicts_caught += (w.verifier or {}).get("verdict") in ("disagree", "rule_fail")
    return {"patients_scored": len(doc_patients), "fields_with_truth": n_fields, "fill_rate": round(n_filled / n_fields, 3) if n_fields else None,
            "accuracy_of_filled": round(n_correct / n_filled, 3) if n_filled else None, "receipt_coverage": round(n_receipt / n_filled, 3) if n_filled else None,
            "planted_conflicts": {"total": conflicts_total, "caught": conflicts_caught, "catch_rate": round(conflicts_caught / conflicts_total, 3) if conflicts_total else None},
            "unit_traps": {"total": traps_total, "converted_correctly": traps_ok}, "gap_fills": {"total": gaps_total, "filled_from_document": gaps_filled},
            "false_alarms": n_false_alarm, "fields_flagged": n_flag, "children_immunizations_complete": f"{kids_ok}/{kids_total}",
            "per_concept": {k: {**v, "accuracy": round(v["correct"] / v["filled"], 3) if v["filled"] else None} for k, v in sorted(per_concept.items())}}



def _match(truth_facts, reader_facts) -> int:
    """Hits between two fact lists: numbers within tolerance on the same concept; text by fuzzy match (>= 85) on the same concept and,
    for vaccines and events, the same date. Each truth fact is matched at most once."""
    from rapidfuzz import fuzz
    from .concepts import numbers_agree
    used, hits = set(), 0
    for t in truth_facts:
        tc, tn, tt, td = t["concept"], t["value_num"], (t["value_text"] or "").strip().lower(), str(t["observed_at"])[:10]
        for j, r in enumerate(reader_facts):
            if j in used or r["concept"] != tc:
                continue
            rn, rt, rd = r["value_num"], (r["value_text"] or "").strip().lower(), str(r["observed_at"])[:10]
            if tn is not None:
                ok = rn is not None and numbers_agree(tc, float(tn), float(rn))
            else:
                ok = fuzz.partial_ratio(tt, rt) >= 85 and (tc not in ("immunization", "adverse_event") or td == rd)
            if ok:
                used.add(j); hits += 1; break
    return hits


def _rows(facts):
    return [f.model_dump() if hasattr(f, "model_dump") else f for f in facts]


def reader_metrics(store, truth: dict, documents: list[dict]) -> dict:
    """Per document kind: what the deployed reader stored versus the answer key, and what a regex baseline would get."""
    from datetime import date, datetime
    from .reader import OracleDocReader, RegexDocReader, extraction_to_facts
    from .schema import Document
    oracle, regex = OracleDocReader(truth["doc_extractions"]), RegexDocReader()
    rows = {}
    reader_names = set()
    for d in documents:
        doc = Document(id=d["id"], patient_id=d["patient_id"], source_org=d["source_org"], kind=d["kind"], received_at=datetime.fromisoformat(d["received_at"]), document_date=date.fromisoformat(d["document_date"]), text=d["text"], n_pages=d["n_pages"])
        tfacts = _rows(extraction_to_facts(doc, oracle.read(doc), "oracle")[0])
        rfacts = _rows(extraction_to_facts(doc, regex.read(doc), "regex")[0])
        stored = store.document(doc.id)
        if not stored:
            continue
        reader_names.add(stored.get("reader") or "")
        mfacts = stored["facts"]
        s_hit, m_hit = _match(tfacts, rfacts), _match(tfacts, mfacts)
        for bucket in (d["kind"], f"all {d.get('layout', 'standard')} layouts"):
            r = rows.setdefault(bucket, {"documents": 0, "truth": 0, "scripts_hit": 0, "scripts_out": 0, "reader_hit": 0, "reader_out": 0, "unlocated": 0})
            r["documents"] += 1; r["truth"] += len(tfacts)
            r["scripts_hit"] += s_hit; r["scripts_out"] += len(rfacts)
            r["reader_hit"] += m_hit; r["reader_out"] += len(mfacts)
            r["unlocated"] += sum(1 for f in mfacts if f["span_start"] is None)
    out = {}
    for k, r in rows.items():
        out[k] = {**r, "scripts_recall": round(r["scripts_hit"] / r["truth"], 3) if r["truth"] else None, "scripts_precision": round(r["scripts_hit"] / r["scripts_out"], 3) if r["scripts_out"] else None,
                  "reader_recall": round(r["reader_hit"] / r["truth"], 3) if r["truth"] else None, "reader_precision": round(r["reader_hit"] / r["reader_out"], 3) if r["reader_out"] else None,
                  "unlocated_rate": round(r["unlocated"] / r["reader_out"], 3) if r["reader_out"] else None}
    tot = {k: sum(r[k] for b, r in rows.items() if not b.startswith("all ")) for k in ("documents", "truth", "scripts_hit", "scripts_out", "reader_hit", "reader_out", "unlocated")}
    out["all"] = {**tot, "scripts_recall": round(tot["scripts_hit"] / tot["truth"], 3) if tot["truth"] else None, "scripts_precision": round(tot["scripts_hit"] / tot["scripts_out"], 3) if tot["scripts_out"] else None,
                  "reader_recall": round(tot["reader_hit"] / tot["truth"], 3) if tot["truth"] else None, "reader_precision": round(tot["reader_hit"] / tot["reader_out"], 3) if tot["reader_out"] else None,
                  "unlocated_rate": round(tot["unlocated"] / tot["reader_out"], 3) if tot["reader_out"] else None}
    return {"reader": ", ".join(sorted(n for n in reader_names if n)), "by_kind": out}


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
    if m.get("reader"):
        rm = m["reader"]
        lines += ["", f"### Document reading: scripts baseline versus reader ({rm['reader']})", "", "| Document kind | Docs | Truth facts | Scripts recall | Scripts precision | Reader recall | Reader precision | Reader quotes not located |", "|---|---|---|---|---|---|---|---|"]
        pct = lambda x: f"{x:.1%}" if x is not None else "-"
        for k, r in rm["by_kind"].items():
            lines.append(f"| {k} | {r['documents']} | {r['truth']} | {pct(r['scripts_recall'])} | {pct(r['scripts_precision'])} | {pct(r['reader_recall'])} | {pct(r['reader_precision'])} | {pct(r['unlocated_rate'])} |")
        lines += ["", "Scripts baseline: hand-written label and value patterns for these document layouts. Precision counts extra facts the reader found that are not in the answer key; a date of birth read from a header counts as extra."]
    if reader == "oracle":
        lines += ["", "Oracle mode uses the answer key as the document reader, so document facts are extracted perfectly by construction. It validates coding, unit conversion, the filler, and the verifier. Run with --reader model for real reading numbers."]
    return "\n".join(lines)
