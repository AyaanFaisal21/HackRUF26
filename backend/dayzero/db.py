"""Tiger Data store. Same Store protocol as MemoryStore; this one is what the API and the demo use.
Vector search uses pgvector's cosine operator with the HNSW index; the time-series pieces are in schema.sql."""
from __future__ import annotations

import json
import os
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .schema import AuditEvent, CaseRecord, DuplicateCandidate, Extraction, Message

SQL_DIR = Path(__file__).resolve().parents[1] / "sql"


def connect():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL is not set (see .env.example)")
    return psycopg.connect(url, row_factory=dict_row, autocommit=True)


def init_schema(conn) -> None:
    conn.execute(open(SQL_DIR / "schema.sql").read())


def _vec(v: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in v) + "]"


class PgStore:
    def __init__(self, conn):
        self.conn = conn

    def save_message(self, msg: Message, embedding, extraction: Extraction):
        self.conn.execute(
            """INSERT INTO messages (id, received_at, channel, language, sender, subject, body, extraction)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (id, received_at) DO UPDATE SET extraction = EXCLUDED.extraction""",
            (msg.id, msg.received_at, msg.channel, extraction.language, msg.sender, msg.subject, msg.body, Jsonb(extraction.model_dump(mode="json"))))
        self.conn.execute("INSERT INTO message_embeddings (message_id, embedding) VALUES (%s, %s::vector) ON CONFLICT (message_id) DO UPDATE SET embedding = EXCLUDED.embedding",
                          (msg.id, _vec(embedding)))

    def candidates(self, embedding, k=10):
        rows = self.conn.execute(
            """SELECT record, 1 - (embedding <=> %s::vector) AS sim FROM cases
               WHERE merged_into IS NULL AND embedding IS NOT NULL ORDER BY embedding <=> %s::vector LIMIT %s""",
            (_vec(embedding), _vec(embedding), k)).fetchall()
        return [(CaseRecord.model_validate(r["record"]), float(r["sim"])) for r in rows]

    def cases_with_drugs(self, names):
        if not names:
            return []
        rows = self.conn.execute(
            """SELECT DISTINCT c.record FROM cases c JOIN case_drugs d ON d.case_id = c.id
               WHERE lower(d.name) = ANY(%s) AND c.merged_into IS NULL""", ([n.lower() for n in names],)).fetchall()
        return [CaseRecord.model_validate(r["record"]) for r in rows]

    def open_invalid_cases(self):
        rows = self.conn.execute("SELECT record FROM cases WHERE NOT valid AND merged_into IS NULL").fetchall()
        return [CaseRecord.model_validate(r["record"]) for r in rows]

    def get_case(self, case_id):
        r = self.conn.execute("SELECT record FROM cases WHERE id = %s", (case_id,)).fetchone()
        return CaseRecord.model_validate(r["record"]) if r else None

    def case_for_message(self, message_id):
        r = self.conn.execute("SELECT case_id FROM messages WHERE id = %s", (message_id,)).fetchone()
        return r["case_id"] if r else None

    def save_case(self, rec: CaseRecord):
        s, a = rec.state, rec.assessment
        self.conn.execute(
            """INSERT INTO cases (id, status, merged_into, patient_identifiable, patient_initials, patient_age, patient_sex,
                   reporter_identifiable, reporter_name, reporter_qualification, event_date, valid, missing, serious, criteria,
                   expectedness, expedited, day_zero, due_date, clock_days, record, embedding)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (id) DO UPDATE SET status=EXCLUDED.status, merged_into=EXCLUDED.merged_into,
                   patient_identifiable=EXCLUDED.patient_identifiable, patient_initials=EXCLUDED.patient_initials,
                   patient_age=EXCLUDED.patient_age, patient_sex=EXCLUDED.patient_sex, reporter_identifiable=EXCLUDED.reporter_identifiable,
                   reporter_name=EXCLUDED.reporter_name, reporter_qualification=EXCLUDED.reporter_qualification, event_date=EXCLUDED.event_date,
                   valid=EXCLUDED.valid, missing=EXCLUDED.missing, serious=EXCLUDED.serious, criteria=EXCLUDED.criteria,
                   expectedness=EXCLUDED.expectedness, expedited=EXCLUDED.expedited, day_zero=EXCLUDED.day_zero, due_date=EXCLUDED.due_date,
                   clock_days=EXCLUDED.clock_days, record=EXCLUDED.record, embedding=EXCLUDED.embedding""",
            (s.case_id, rec.status, rec.merged_into, s.patient.identifiable, s.patient.initials, s.patient.age, s.patient.sex,
             s.reporter.identifiable, s.reporter.name, s.reporter.qualification, s.event_date[:10] if s.event_date else None,
             a.valid, a.missing, a.serious, a.criteria, a.expectedness, a.expedited, a.day_zero, a.due_date, a.clock_days,
             Jsonb(rec.model_dump(mode="json")), _vec(rec.embedding) if rec.embedding else None))
        self.conn.execute("DELETE FROM case_drugs WHERE case_id = %s", (s.case_id,))
        self.conn.execute("DELETE FROM case_reactions WHERE case_id = %s", (s.case_id,))
        for d in s.drugs:
            self.conn.execute("INSERT INTO case_drugs VALUES (%s,%s,%s,%s,%s)", (s.case_id, d.name, d.role, d.dose, d.start_date))
        for r in s.reactions:
            self.conn.execute("INSERT INTO case_reactions VALUES (%s,%s,%s,%s,%s)", (s.case_id, r.term, r.pt, r.outcome, r.onset_date))
        for snap in s.snapshots:
            self.conn.execute("UPDATE messages SET case_id = %s WHERE id = %s", (s.case_id, snap.message_id))

    def save_duplicate(self, c: DuplicateCandidate):
        self.conn.execute(
            """INSERT INTO case_duplicates (case_id, other_case_id, score, structured, semantic, evidence, verdict)
               VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (case_id, other_case_id) DO UPDATE SET score = EXCLUDED.score""",
            (c.case_id, c.other_case_id, c.score, c.structured, c.semantic, Jsonb(c.evidence), c.verdict))

    def audit(self, ev: AuditEvent):
        self.conn.execute(
            "INSERT INTO case_audit (case_id, at, actor, action, field, old_value, new_value, message_id, reason) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (ev.case_id, ev.at, ev.actor, ev.action, ev.field, Jsonb(ev.old), Jsonb(ev.new), ev.message_id, ev.reason))

    def next_case_id(self):
        r = self.conn.execute("SELECT max(substring(id from 4)::int) AS m FROM cases").fetchone()
        return f"DZ-{(r['m'] or 0) + 1:04d}"

    # ---- read side used by the API
    def queue(self):
        return self.conn.execute("SELECT * FROM queue").fetchall()

    def case_detail(self, case_id):
        rec = self.conn.execute("SELECT record, status, merged_into FROM cases WHERE id = %s", (case_id,)).fetchone()
        if not rec:
            return None
        msgs = self.conn.execute("SELECT id, received_at, channel, sender, subject, body, extraction FROM messages WHERE case_id = %s ORDER BY received_at", (case_id,)).fetchall()
        dups = self.conn.execute("SELECT * FROM case_duplicates WHERE case_id = %s OR other_case_id = %s ORDER BY score DESC", (case_id, case_id)).fetchall()
        return {"case": rec["record"], "status": rec["status"], "merged_into": rec["merged_into"], "messages": msgs, "duplicates": dups}

    def history(self, case_id):
        return self.conn.execute("SELECT * FROM case_audit WHERE case_id = %s ORDER BY at", (case_id,)).fetchall()

    def intake_series(self, days=30):
        self.conn.execute("CALL refresh_continuous_aggregate('intake_hourly', now() - INTERVAL '%s days', now())" % int(days))
        return self.conn.execute("SELECT bucket, channel, n FROM intake_hourly WHERE bucket > now() - INTERVAL '%s days' ORDER BY bucket" % int(days)).fetchall()

    def stats(self):
        q = """SELECT (SELECT count(*) FROM messages) AS messages, (SELECT count(*) FROM cases WHERE merged_into IS NULL) AS cases,
                      (SELECT count(*) FROM cases WHERE expedited AND due_date < CURRENT_DATE AND status <> 'closed') AS overdue,
                      (SELECT count(*) FROM case_duplicates WHERE decided IS NULL) AS open_duplicates,
                      (SELECT count(*) FROM case_audit) AS audit_events"""
        base = self.conn.execute(q).fetchone()
        comp = self.conn.execute("SELECT * FROM hypertable_compression_stats('messages')").fetchone()
        return {**base, "compression": {k: comp[k] for k in ("total_chunks", "number_compressed_chunks")} if comp else None}
