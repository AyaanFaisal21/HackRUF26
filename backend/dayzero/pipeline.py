"""Orchestration. One message at a time: extract -> code -> embed -> resolve follow-up or find duplicates ->
build case -> assess -> persist + audit. Storage is behind the Store protocol so the same pipeline runs in memory
(tests, evaluation) and against Tiger Data (API, demo)."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Protocol

from .coding import Coder
from .dedupe import combined
from .embed import cosine
from .rules import assess, merge_snapshots
from .schema import AuditEvent, CaseRecord, DuplicateCandidate, Extraction, Message, Snapshot

ID_RE = re.compile(r"(MSG-\d{4}(?:-FU|-DUP)?|DZ-\d{4})")
FOLLOWUP_MIN = 0.5


class Store(Protocol):
    def save_message(self, msg: Message, embedding: list[float], extraction: Extraction) -> None: ...
    def candidates(self, embedding: list[float], k: int = 25) -> list[tuple[CaseRecord, float]]: ...
    def cases_with_drugs(self, names: list[str]) -> list[CaseRecord]: ...
    def open_invalid_cases(self) -> list[CaseRecord]: ...
    def get_case(self, case_id: str) -> CaseRecord | None: ...
    def case_for_message(self, message_id: str) -> str | None: ...
    def save_case(self, rec: CaseRecord) -> None: ...
    def save_duplicate(self, cand: DuplicateCandidate) -> None: ...
    def audit(self, ev: AuditEvent) -> None: ...
    def next_case_id(self) -> str: ...


class MemoryStore:
    def __init__(self):
        self.messages: dict[str, tuple[Message, list[float], Extraction]] = {}
        self.cases: dict[str, CaseRecord] = {}
        self.msg_case: dict[str, str] = {}
        self.duplicates: list[DuplicateCandidate] = []
        self.audit_log: list[AuditEvent] = []

    def save_message(self, msg, embedding, extraction):
        self.messages[msg.id] = (msg, embedding, extraction)

    def _open(self):
        return [r for r in self.cases.values() if r.merged_into is None]

    def candidates(self, embedding, k=25):
        scored = [(rec, cosine(embedding, rec.embedding)) for rec in self._open() if rec.embedding]
        return sorted(scored, key=lambda x: -x[1])[:k]

    def cases_with_drugs(self, names):
        want = {n.lower() for n in names}
        return [r for r in self._open() if want & {d.name.lower() for d in r.state.drugs}]

    def open_invalid_cases(self):
        return [r for r in self._open() if not r.assessment.valid]

    def get_case(self, case_id):
        return self.cases.get(case_id)

    def case_for_message(self, message_id):
        return self.msg_case.get(message_id)

    def save_case(self, rec):
        self.cases[rec.state.case_id] = rec
        for s in rec.state.snapshots:
            self.msg_case[s.message_id] = rec.state.case_id

    def save_duplicate(self, cand):
        self.duplicates.append(cand)

    def audit(self, ev):
        self.audit_log.append(ev)

    def next_case_id(self):
        return f"DZ-{len(self.cases):04d}"


def followup_score(msg: Message, ext: Extraction, cand: CaseRecord, sim: float) -> tuple[float, dict]:
    """How well a follow-up message fits an existing case. Follow-ups rarely restate drugs and reactions, so the
    duplicate scorer does not apply; instead we look for the case's product or initials in the text, whether the
    message supplies exactly what the case is missing, recency, and semantic similarity."""
    text = f"{msg.subject or ''} {msg.body} {ext.followup_reference or ''}".lower()
    ev = {}
    drugs = [d.name.lower() for d in cand.state.drugs]
    ev["drug_mentioned"] = 1.0 if any(d and d in text for d in drugs) else 0.0
    ini = cand.state.patient.initials
    ev["initials_mentioned"] = 1.0 if ini and ini.lower() in text else 0.0
    supplies = set()
    if ext.reporter.identifiable: supplies.add("identifiable_reporter")
    if ext.patient.identifiable: supplies.add("identifiable_patient")
    if ext.drugs: supplies.add("suspect_drug")
    if ext.reactions: supplies.add("adverse_event")
    missing = set(cand.assessment.missing)
    ev["supplies_missing"] = 1.0 if missing and missing <= supplies else 0.5 if missing & supplies else 0.0
    last = max(s.received_at for s in cand.state.snapshots)
    ev["recent"] = 1.0 if timedelta(0) <= (msg.received_at - last) <= timedelta(days=14) else 0.0
    ev["semantic"] = round(max(sim, 0.0), 3)
    score = 0.4 * ev["drug_mentioned"] + 0.25 * ev["initials_mentioned"] + 0.2 * ev["supplies_missing"] + 0.1 * ev["recent"] + 0.1 * ev["semantic"]
    return round(score, 3), ev


class Pipeline:
    def __init__(self, store: Store, extractor, embedder, coder: Coder | None = None, rsi: dict | None = None):
        self.store, self.extractor, self.embedder = store, extractor, embedder
        self.coder = coder or Coder()
        self.rsi = rsi or {}

    def _now(self):
        return datetime.now(timezone.utc)

    def _pool(self, emb, drug_names):
        """Candidate pool = vector neighbours (pgvector) + same-product cases (relational). Dict keyed by case id."""
        pool = {rec.state.case_id: (rec, sim) for rec, sim in self.store.candidates(emb)}
        for rec in self.store.cases_with_drugs(drug_names):
            pool.setdefault(rec.state.case_id, (rec, cosine(emb, rec.embedding) if rec.embedding else 0.0))
        return pool

    def _resolve_followup(self, msg, ext, emb) -> tuple[CaseRecord | None, dict]:
        m = ID_RE.search(ext.followup_reference or "") or ID_RE.search(msg.body)
        if m:
            cid = m.group(1)
            rec = self.store.get_case(cid)
            if rec is None and self.store.case_for_message(cid):
                rec = self.store.get_case(self.store.case_for_message(cid))
            if rec is not None:
                return rec, {"explicit_reference": cid}
        pool = self._pool(emb, [d.name for d in ext.drugs])
        for rec in self.store.open_invalid_cases():
            pool.setdefault(rec.state.case_id, (rec, cosine(emb, rec.embedding) if rec.embedding else 0.0))
        best, best_ev = None, {}
        for rec, sim in pool.values():
            score, ev = followup_score(msg, ext, rec, sim)
            if score >= FOLLOWUP_MIN and (best is None or score > best[1]):
                best, best_ev = (rec, score), ev
        return (best[0], {"match_score": best[1], **best_ev}) if best else (None, {})

    def process(self, msg: Message) -> CaseRecord:
        ext = self.extractor.extract(msg)
        emb = self.embedder.embed(msg.body)
        self.store.save_message(msg, emb, ext)
        snap = Snapshot(message_id=msg.id, received_at=msg.received_at, extraction=ext)

        if ext.is_followup:
            target, how = self._resolve_followup(msg, ext, emb)
            if target is not None:
                old = target.assessment.model_dump(mode="json")
                state = merge_snapshots(target.state.case_id, target.state.snapshots + [snap], self.coder)
                rec = CaseRecord(state=state, assessment=assess(state, self.rsi, self.coder), status=target.status, embedding=target.embedding)
                self.store.save_case(rec)
                self.store.audit(AuditEvent(case_id=rec.state.case_id, at=self._now(), actor="pipeline", action="followup_merged", message_id=msg.id,
                                            old=old, new=rec.assessment.model_dump(mode="json"), reason=f"follow-up matched: {how}"))
                return rec

        cid = self.store.next_case_id()
        state = merge_snapshots(cid, [snap], self.coder)
        rec = CaseRecord(state=state, assessment=assess(state, self.rsi, self.coder), embedding=emb)
        self.store.save_case(rec)
        self.store.audit(AuditEvent(case_id=cid, at=self._now(), actor="pipeline", action="created", message_id=msg.id,
                                    new=rec.assessment.model_dump(mode="json"), reason="unmatched follow-up, opened as new case" if ext.is_followup else None))
        for other, sim in self._pool(emb, [d.name for d in state.drugs]).values():
            if other.state.case_id == cid:
                continue
            c = combined(state, other.state, emb, other.embedding)
            if c:
                self.store.save_duplicate(c)
        return rec

    def process_many(self, messages: list[Message]) -> list[CaseRecord]:
        return [self.process(m) for m in sorted(messages, key=lambda m: m.received_at)]


def confirm_field(store: Store, case_id: str, field: str, new_value, actor: str, reason: str | None = None) -> CaseRecord:
    """Human review action. Records old and new value; never silently overwrites."""
    rec = store.get_case(case_id)
    if rec is None:
        raise KeyError(case_id)
    old = rec.model_dump(mode="json")["state"].get(field)
    rec.status = "in_review" if rec.status == "new" else rec.status
    store.audit(AuditEvent(case_id=case_id, at=datetime.now(timezone.utc), actor=actor, action="field_edited" if new_value != old else "field_confirmed",
                           field=field, old=old, new=new_value, reason=reason))
    store.save_case(rec)
    return rec


def merge_cases(store: Store, keep_id: str, drop_id: str, actor: str, coder: Coder, rsi: dict) -> CaseRecord:
    keep, drop = store.get_case(keep_id), store.get_case(drop_id)
    if keep is None or drop is None:
        raise KeyError(f"{keep_id} or {drop_id}")
    state = merge_snapshots(keep_id, keep.state.snapshots + drop.state.snapshots, coder)
    merged = CaseRecord(state=state, assessment=assess(state, rsi, coder), status=keep.status, embedding=keep.embedding)
    drop.merged_into, drop.status = keep_id, "merged"
    store.save_case(merged)
    store.save_case(drop)
    now = datetime.now(timezone.utc)
    store.audit(AuditEvent(case_id=keep_id, at=now, actor=actor, action="merged", new=drop_id, reason="human confirmed duplicate"))
    store.audit(AuditEvent(case_id=drop_id, at=now, actor=actor, action="merged_into", new=keep_id))
    return merged
