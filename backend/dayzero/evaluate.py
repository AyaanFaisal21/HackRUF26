"""Score the pipeline against the answer key. Produces the numbers for the deck."""
from __future__ import annotations

from .coding import Coder
from .pipeline import MemoryStore
from .schema import Extraction


def _set_drugs(e: Extraction):
    return {d.name.strip().lower() for d in e.drugs if d.role == "suspect"}


def _set_reactions(e: Extraction, coder: Coder):
    return {(coder.code(r.term)[0] or r.term).lower() for r in e.reactions}


def evaluate(store: MemoryStore, answer_key: dict, coder: Coder) -> dict:
    fields = {"patient.identifiable": 0, "reporter.identifiable": 0, "patient.age": 0, "patient.sex": 0, "suspect_drugs": 0, "reactions": 0, "seriousness": 0, "is_followup": 0}
    n = 0
    for mid, (msg, emb, pred) in store.messages.items():
        truth = Extraction.model_validate(answer_key[mid]["extraction"])
        n += 1
        fields["patient.identifiable"] += pred.patient.identifiable == truth.patient.identifiable
        fields["reporter.identifiable"] += pred.reporter.identifiable == truth.reporter.identifiable
        fields["patient.age"] += pred.patient.age == truth.patient.age
        fields["patient.sex"] += pred.patient.sex == truth.patient.sex
        fields["suspect_drugs"] += _set_drugs(pred) == _set_drugs(truth)
        fields["reactions"] += _set_reactions(pred, coder) == _set_reactions(truth, coder)
        fields["seriousness"] += pred.seriousness.model_dump(exclude={"evidence"}) == truth.seriousness.model_dump(exclude={"evidence"})
        fields["is_followup"] += pred.is_followup == truth.is_followup
    field_acc = {k: round(v / n, 3) for k, v in fields.items()} if n else {}

    # validity and day zero per case: a case is valid iff its root message variant is complete, or it received its follow-up
    val_ok = dz_ok = cases = 0
    for cid, rec in store.cases.items():
        if rec.merged_into:
            continue
        cases += 1
        root = rec.state.snapshots[0].message_id
        k = answer_key[root]
        expected_valid = k["variant"] in ("complete", "duplicate") or any(answer_key[s.message_id]["variant"] == "followup" for s in rec.state.snapshots)
        val_ok += rec.assessment.valid == expected_valid
        expected_dz = min((s.received_at for s in rec.state.snapshots if answer_key[s.message_id]["variant"] in ("complete", "duplicate", "followup")), default=None)
        dz_ok += (rec.assessment.day_zero == (expected_dz.date() if expected_dz else None))
    # follow-up attachment
    fu_total = fu_ok = 0
    for mid, k in answer_key.items():
        if k["variant"] == "followup":
            fu_total += 1
            fu_ok += store.msg_case.get(mid) is not None and store.msg_case.get(mid) == store.msg_case.get(k["followup_of"])
    # duplicates: planted pairs vs candidates surfaced (verdict likely or possible)
    planted = {(k["duplicate_of"], mid) for mid, k in answer_key.items() if k["duplicate_of"]}
    surfaced = set()
    for c in store.duplicates:
        a = store.cases[c.case_id].state.snapshots[0].message_id
        b = store.cases[c.other_case_id].state.snapshots[0].message_id
        surfaced.add((b, a)); surfaced.add((a, b))
    tp = sum(1 for p in planted if p in surfaced)
    fp = len({tuple(sorted(x)) for x in surfaced}) - tp
    return {"messages": n, "field_accuracy": field_acc, "cases": cases, "validity_accuracy": round(val_ok / cases, 3) if cases else None,
            "day_zero_accuracy": round(dz_ok / cases, 3) if cases else None,
            "followup_attachment": {"total": fu_total, "correct": fu_ok},
            "duplicates": {"planted": len(planted), "found": tp, "recall": round(tp / len(planted), 3) if planted else None, "false_positive_pairs": fp}}


def to_markdown(m: dict, extractor_name: str) -> str:
    lines = [f"## Evaluation ({extractor_name})", "", f"Messages: {m['messages']}  Cases: {m['cases']}", "", "| Field | Accuracy |", "|---|---|"]
    lines += [f"| {k} | {v:.1%} |" for k, v in m["field_accuracy"].items()]
    lines += ["", f"Validity decision accuracy: {m['validity_accuracy']:.1%}", f"Day zero accuracy: {m['day_zero_accuracy']:.1%}",
              f"Follow-ups attached to the right case: {m['followup_attachment']['correct']}/{m['followup_attachment']['total']}",
              f"Planted duplicates surfaced: {m['duplicates']['found']}/{m['duplicates']['planted']} (false positive pairs: {m['duplicates']['false_positive_pairs']})"]
    if extractor_name == "oracle":
        lines += ["", "Oracle mode uses the answer key as the extractor, so field accuracy is 100% by construction. It validates everything downstream of extraction. Run with DAYZERO_EXTRACTOR=claude for real extraction numbers."]
    return "\n".join(lines)
