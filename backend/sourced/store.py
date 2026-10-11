"""Tiger Data store for the ledger, documents, forms and audit. MemoryStore implements the read side for tests."""
from __future__ import annotations

import io
import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb as _Jsonb

from .schema import Document, Fact, FormInstance

SQL_DIR = Path(__file__).resolve().parents[1] / "sql"
LEGACY_TABLES = ("case_duplicates", "case_audit", "case_reactions", "case_drugs", "cases", "message_embeddings", "messages", "fda_forms", "briefs", "flags",
                 "subject_events", "lab_results", "diary_entries", "subjects", "trials")


def J(obj):
    return None if obj is None else _Jsonb(json.loads(json.dumps(obj, default=str).replace("\\u0000", "")))


def connect():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL is not set (see .env.example)")
    return psycopg.connect(url, row_factory=dict_row, autocommit=True)


def _vec(v):
    return "[" + ",".join(f"{x:.6f}" for x in v) + "]"


def _day(d: date) -> datetime:
    return datetime.combine(d, datetime.min.time(), tzinfo=timezone.utc)


class MemoryStore:
    """Read-side only; enough for the filler and verifier tests."""

    def __init__(self, facts: list[Fact]):
        self._facts = []
        for i, f in enumerate(facts):
            d = f.model_dump()
            d["id"] = i + 1
            self._facts.append(d)

    def facts(self, patient_id, concept, start, end):
        return sorted([f for f in self._facts if f["patient_id"] == patient_id and f["concept"] == concept and start <= f["observed_at"] <= end and f["status"] != "rejected"],
                      key=lambda f: f["observed_at"], reverse=True)


class Store:
    def __init__(self, conn=None):
        self.conn = conn or connect()

    # ---- schema
    def init_schema(self):
        self.conn.execute(open(SQL_DIR / "sourced.sql").read())

    def drop_legacy(self):
        for v in ("intake_hourly", "diary_weekly"):
            self.conn.execute(f"DROP MATERIALIZED VIEW IF EXISTS {v} CASCADE")
        self.conn.execute("DROP VIEW IF EXISTS queue")
        for t in LEGACY_TABLES:
            self.conn.execute(f"DROP TABLE IF EXISTS {t} CASCADE")

    def reset(self):
        self.conn.execute("SET timescaledb.max_tuples_decompressed_per_dml_transaction = 0")
        self.conn.execute("SELECT decompress_chunk(c, true) FROM show_chunks('facts') c")
        for t in ("form_fields", "form_instances", "facts", "document_chunks", "documents", "patient_identifiers", "patients", "audit_log"):
            self.conn.execute(f"DELETE FROM {t}")

    # ---- writes
    def insert_patients(self, patients: list[dict]):
        for p in patients:
            self.conn.execute("""INSERT INTO patients (id, display_name, birth_date, sex, race, kind, trial_id, site, ref_date) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                                 ON CONFLICT (id) DO UPDATE SET display_name = EXCLUDED.display_name, birth_date = EXCLUDED.birth_date""",
                              (p["id"], p.get("display_name"), p.get("birth_date"), p.get("sex"), p.get("race"), p.get("kind", "adult"), p.get("trial_id"), p.get("site"), p.get("ref_date")))

    def insert_identifiers(self, ids: list[dict]):
        for i in ids:
            self.conn.execute("INSERT INTO patient_identifiers VALUES (%s,%s,%s) ON CONFLICT DO NOTHING", (i["patient_id"], i["org"], i["local_id"]))

    def insert_document(self, doc: Document, sha256: str, embedder=None):
        self.conn.execute("""INSERT INTO documents (id, patient_id, source_org, kind, received_at, document_date, sha256, text, n_pages)
                             VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING""",
                          (doc.id, doc.patient_id, doc.source_org, doc.kind, doc.received_at, doc.document_date, sha256, doc.text.replace("\x00", ""), doc.n_pages))
        if embedder is not None:
            for p, page in enumerate(doc.text.split("\f"), start=1):
                paras = [x for x in page.split("\n\n") if x.strip()] or [page]
                for ci, chunk in enumerate(paras):
                    self.conn.execute("INSERT INTO document_chunks (document_id, patient_id, page, chunk_index, text, embedding) VALUES (%s,%s,%s,%s,%s,%s::vector)",
                                      (doc.id, doc.patient_id, p, ci, chunk[:2000], _vec(embedder.embed(chunk))))

    def mark_document(self, doc_id: str, status: str, reader: str | None, n_facts: int | None):
        self.conn.execute("UPDATE documents SET status = %s, reader = %s, n_facts = %s, read_at = now() WHERE id = %s", (status, reader, n_facts, doc_id))

    def insert_facts(self, facts: list[Fact]) -> int:
        if not facts:
            return 0
        cols = ["patient_id", "concept", "display", "value_num", "value_text", "unit", "observed_at", "end_at", "attrs", "source_org", "document_id", "page", "span_start", "span_end", "quote", "resource_ref", "extractor", "confidence", "status"]
        buf = io.StringIO()
        for f in facts:
            row = [f.patient_id, f.concept, f.display, f.value_num, f.value_text, f.unit, _day(f.observed_at).isoformat(), _day(f.end_at).isoformat() if f.end_at else None,
                   json.dumps(f.attrs, default=str), f.source_org, f.document_id, f.page, f.span_start, f.span_end, f.quote, f.resource_ref, f.extractor, f.confidence, f.status]
            buf.write("\t".join("\\N" if v is None else str(v).replace("\x00", "").replace("\\", "\\\\").replace("\t", " ").replace("\n", " ") for v in row) + "\n")
        buf.seek(0)
        with self.conn.cursor() as cur, cur.copy(f"COPY facts ({', '.join(cols)}) FROM STDIN") as cp:
            cp.write(buf.read())
        return len(facts)

    def refresh_aggregates(self):
        try:
            self.conn.execute("CALL refresh_continuous_aggregate('facts_daily', NULL, NULL)")
        except psycopg.errors.LockNotAvailable:
            pass

    def upsert_form_defs(self, defs):
        for d in defs:
            self.conn.execute("INSERT INTO form_definitions (id, name, domain, description, fields) VALUES (%s,%s,%s,%s,%s) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, domain = EXCLUDED.domain, description = EXCLUDED.description, fields = EXCLUDED.fields",
                              (d.id, d.name, d.domain, d.description, J([f.model_dump() for f in d.fields])))

    def audit(self, actor, action, entity=None, entity_id=None, field=None, old=None, new=None, reason=None):
        self.conn.execute("INSERT INTO audit_log (actor, action, entity, entity_id, field, old_value, new_value, reason) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                          (actor, action, entity, str(entity_id) if entity_id is not None else None, field, J(old), J(new), reason))

    # ---- ledger reads
    def facts(self, patient_id: str, concept: str, start: date, end: date) -> list[dict]:
        rows = self.conn.execute("""SELECT id, patient_id, concept, display, value_num, value_text, unit, observed_at::date AS observed_at, end_at::date AS end_at, attrs, source_org, document_id, page,
                                           span_start, span_end, quote, resource_ref, extractor, confidence, status
                                    FROM facts WHERE patient_id = %s AND concept = %s AND observed_at >= %s AND observed_at < %s AND status <> 'rejected' ORDER BY observed_at DESC, confidence DESC""",
                                 (patient_id, concept, _day(start), _day(end + timedelta(days=1)))).fetchall()
        return rows

    def facts_for_patient(self, patient_id: str, concept: str | None = None, limit: int = 2000):
        q = """SELECT id, concept, display, value_num, value_text, unit, observed_at::date AS observed_at, end_at::date AS end_at, attrs, source_org, document_id, page, span_start, span_end, quote, resource_ref, extractor, confidence, status
               FROM facts WHERE patient_id = %s""" + (" AND concept = %s" if concept else "") + " ORDER BY observed_at DESC LIMIT %s"
        return self.conn.execute(q, (patient_id, concept, limit) if concept else (patient_id, limit)).fetchall()

    def patients(self, q: str | None = None, kind: str | None = None):
        return self.conn.execute("""SELECT p.id, p.display_name, p.birth_date, p.sex, p.kind, p.trial_id, p.site,
                                           (SELECT count(DISTINCT org) FROM patient_identifiers i WHERE i.patient_id = p.id) AS n_orgs,
                                           (SELECT count(*) FROM documents d WHERE d.patient_id = p.id) AS n_documents,
                                           (SELECT count(*) FROM facts f WHERE f.patient_id = p.id) AS n_facts,
                                           (SELECT count(*) FROM form_instances fi WHERE fi.patient_id = p.id AND fi.status <> 'signed') AS forms_open,
                                           (SELECT coalesce(sum(n_flagged), 0) FROM form_instances fi WHERE fi.patient_id = p.id AND fi.status <> 'signed') AS flagged
                                    FROM patients p WHERE (%s::text IS NULL OR p.id ILIKE %s OR p.display_name ILIKE %s) AND (%s::text IS NULL OR p.kind = %s)
                                    ORDER BY n_documents DESC, flagged DESC, p.id LIMIT 400""", (q, f"%{q}%" if q else None, f"%{q}%" if q else None, kind, kind)).fetchall()

    def patient(self, patient_id: str):
        p = self.conn.execute("SELECT * FROM patients WHERE id = %s", (patient_id,)).fetchone()
        if not p:
            return None
        ids = self.conn.execute("SELECT org, local_id FROM patient_identifiers WHERE patient_id = %s ORDER BY org", (patient_id,)).fetchall()
        docs = self.conn.execute("SELECT id, source_org, kind, received_at, document_date, n_pages, status, reader, n_facts FROM documents WHERE patient_id = %s ORDER BY document_date DESC", (patient_id,)).fetchall()
        concepts = self.conn.execute("""SELECT concept, display, count(*) AS n, count(DISTINCT source_org) AS n_sources, max(observed_at)::date AS latest, array_agg(DISTINCT source_org) AS sources
                                        FROM facts WHERE patient_id = %s AND status <> 'rejected' GROUP BY concept, display ORDER BY n DESC""", (patient_id,)).fetchall()
        forms = self.conn.execute("""SELECT fi.id, fi.form_id, fd.name, fd.domain, fi.visit_date, fi.status, fi.n_fields, fi.n_filled, fi.n_flagged, fi.filled_ms, fi.signed_by, fi.created_at
                                     FROM form_instances fi JOIN form_definitions fd ON fd.id = fi.form_id WHERE fi.patient_id = %s ORDER BY fi.visit_date DESC, fi.id DESC""", (patient_id,)).fetchall()
        visits = self.conn.execute("SELECT DISTINCT observed_at::date AS d FROM facts WHERE patient_id = %s AND concept IN ('sbp','alt','weight') ORDER BY d DESC LIMIT 40", (patient_id,)).fetchall()
        return {"patient": p, "identifiers": ids, "documents": docs, "concepts": concepts, "forms": forms, "visit_dates": [v["d"] for v in visits]}

    def documents(self, status: str | None = None, limit: int = 300):
        return self.conn.execute("""SELECT d.id, d.patient_id, p.display_name, d.source_org, d.kind, d.received_at, d.document_date, d.n_pages, d.status, d.reader, d.n_facts
                                    FROM documents d LEFT JOIN patients p ON p.id = d.patient_id WHERE (%s::text IS NULL OR d.status = %s) ORDER BY d.received_at DESC LIMIT %s""", (status, status, limit)).fetchall()

    def document(self, doc_id: str):
        d = self.conn.execute("SELECT * FROM documents WHERE id = %s", (doc_id,)).fetchone()
        if not d:
            return None
        facts = self.conn.execute("""SELECT id, concept, display, value_num, value_text, unit, observed_at::date AS observed_at, attrs, page, span_start, span_end, quote, confidence, status
                                     FROM facts WHERE document_id = %s ORDER BY span_start NULLS LAST""", (doc_id,)).fetchall()
        return {**d, "facts": facts}

    def search_chunks(self, embedding, k=8, patient_id=None):
        return self.conn.execute("""SELECT c.document_id, c.patient_id, c.page, c.text, 1 - (c.embedding <=> %s::vector) AS score, d.source_org, d.kind
                                    FROM document_chunks c JOIN documents d ON d.id = c.document_id WHERE (%s::text IS NULL OR c.patient_id = %s)
                                    ORDER BY c.embedding <=> %s::vector LIMIT %s""", (_vec(embedding), patient_id, patient_id, _vec(embedding), k)).fetchall()

    # ---- forms
    def save_instance(self, inst: FormInstance) -> int:
        r = self.conn.execute("""INSERT INTO form_instances (form_id, patient_id, visit_date, status, filled_ms, n_fields, n_filled, n_flagged)
                                 VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""", (inst.form_id, inst.patient_id, inst.visit_date, inst.status, inst.filled_ms, inst.n_fields, inst.n_filled, inst.n_flagged)).fetchone()
        iid = r["id"]
        for f in inst.fields:
            self.conn.execute("""INSERT INTO form_fields (instance_id, key, label, vtype, unit, value, fact_id, confidence, receipt, alternatives, rows, verifier, decision)
                                 VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                              (iid, f.key, f.label, f.vtype, f.unit, J(f.value), f.fact_id, f.confidence, J(f.receipt), J(f.alternatives), J(f.rows), J(f.verifier), J(f.decision)))
        return iid

    def instance(self, iid: int):
        i = self.conn.execute("""SELECT fi.*, fd.name, fd.domain, fd.description, fd.fields AS field_defs, p.display_name
                                 FROM form_instances fi JOIN form_definitions fd ON fd.id = fi.form_id JOIN patients p ON p.id = fi.patient_id WHERE fi.id = %s""", (iid,)).fetchone()
        if not i:
            return None
        fields = self.conn.execute("SELECT * FROM form_fields WHERE instance_id = %s", (iid,)).fetchall()
        order = {fd["key"]: n for n, fd in enumerate(i["field_defs"])}
        fields.sort(key=lambda f: order.get(f["key"], 99))
        return {**i, "fields": fields}

    def decide_field(self, iid: int, key: str, decision: dict):
        f = self.conn.execute("SELECT * FROM form_fields WHERE instance_id = %s AND key = %s", (iid, key)).fetchone()
        if not f:
            raise KeyError(key)
        old = {"value": f["value"], "fact_id": f["fact_id"]}
        value, fact_id, receipt = f["value"], f["fact_id"], f["receipt"]
        if decision["action"] == "choose":
            alt = next((a for a in (f["alternatives"] or []) if a["receipt"]["id"] == decision.get("fact_id")), None)
            if alt:
                value, fact_id, receipt = alt["value"], alt["receipt"]["id"], alt["receipt"]
        elif decision["action"] == "manual":
            value, fact_id, receipt = decision.get("value"), None, {"source_org": "manual entry", "quote": decision.get("reason")}
        elif decision["action"] == "blank":
            value, fact_id, receipt = None, None, None
        self.conn.execute("UPDATE form_fields SET value = %s, fact_id = %s, receipt = %s, decision = %s WHERE instance_id = %s AND key = %s", (J(value), fact_id, J(receipt), J(decision), iid, key))
        self.conn.execute("UPDATE form_instances SET status = 'in_review' WHERE id = %s AND status = 'draft'", (iid,))
        self.audit(decision.get("actor", "reviewer"), f"field_{decision['action']}", "form_instance", iid, key, old, {"value": value, "fact_id": fact_id}, decision.get("reason"))
        return self.conn.execute("SELECT * FROM form_fields WHERE instance_id = %s AND key = %s", (iid, key)).fetchone()

    def unresolved(self, iid: int) -> list[str]:
        fields = self.conn.execute("SELECT key, verifier, decision FROM form_fields WHERE instance_id = %s", (iid,)).fetchall()
        return [f["key"] for f in fields if (f["verifier"] or {}).get("verdict") in ("disagree", "rule_fail", "missing") and not f["decision"]]

    def sign(self, iid: int, actor: str) -> dict:
        pending = self.unresolved(iid)
        if pending:
            raise ValueError(f"unresolved fields: {', '.join(pending)}")
        inst = self.instance(iid)
        export = {"ODM": {"ClinicalData": {"StudyOID": "CDISCPILOT01", "SubjectData": {"SubjectKey": inst["patient_id"], "StudyEventData": {"StudyEventOID": inst["domain"], "StartDate": inst["visit_date"].isoformat()},
                  "FormData": {"FormOID": inst["form_id"], "SignedBy": actor, "SignedAt": datetime.now(timezone.utc).isoformat(), "ItemGroupData": [
                      {"ItemOID": f["key"], "Value": f["value"] if f["vtype"] != "list" else None, "Rows": f["rows"] if f["vtype"] == "list" else None, "Unit": f["unit"],
                       "Receipt": f["receipt"], "Verifier": (f["verifier"] or {}).get("verdict"), "Decision": f["decision"]} for f in inst["fields"]]}}}}}
        self.conn.execute("UPDATE form_instances SET status = 'signed', signed_by = %s, signed_at = now(), export = %s WHERE id = %s", (actor, J(export), iid))
        self.audit(actor, "form_signed", "form_instance", iid, None, None, {"fields": len(inst["fields"])})
        return self.instance(iid)

    def queue(self):
        return self.conn.execute("""SELECT fi.id, fi.form_id, fd.name, fd.domain, fi.patient_id, p.display_name, p.kind, fi.visit_date, fi.status, fi.n_fields, fi.n_filled, fi.n_flagged, fi.filled_ms, fi.created_at,
                                           (SELECT count(*) FROM form_fields ff WHERE ff.instance_id = fi.id AND (ff.verifier->>'verdict') IN ('disagree','rule_fail','missing') AND ff.decision IS NULL) AS unresolved
                                    FROM form_instances fi JOIN form_definitions fd ON fd.id = fi.form_id JOIN patients p ON p.id = fi.patient_id
                                    WHERE fi.status <> 'signed' ORDER BY unresolved DESC, fi.n_flagged DESC, fi.created_at DESC LIMIT 300""").fetchall()

    def history(self, entity: str, entity_id: str):
        return self.conn.execute("SELECT * FROM audit_log WHERE entity = %s AND entity_id = %s ORDER BY at", (entity, str(entity_id))).fetchall()

    def stats(self):
        base = self.conn.execute("""SELECT (SELECT count(*) FROM patients) AS patients, (SELECT count(*) FROM documents) AS documents, (SELECT count(*) FROM documents WHERE status = 'read') AS documents_read,
                                           (SELECT count(*) FROM facts) AS facts, (SELECT count(DISTINCT source_org) FROM facts) AS sources,
                                           (SELECT count(*) FROM form_instances) AS forms, (SELECT count(*) FROM form_instances WHERE status = 'signed') AS forms_signed,
                                           (SELECT count(*) FROM audit_log) AS audit_events""").fetchone()
        comp = self.conn.execute("SELECT * FROM hypertable_compression_stats('facts')").fetchone()
        size = self.conn.execute("SELECT pg_size_pretty(hypertable_size('facts')) AS s").fetchone()["s"]
        by_org = self.conn.execute("SELECT source_org, count(*) AS n FROM facts GROUP BY source_org ORDER BY n DESC").fetchall()
        return {**base, "facts_size": size, "compression": {k: comp[k] for k in ("total_chunks", "number_compressed_chunks")} if comp else None, "facts_by_source": by_org}

    def facts_daily(self, days=400):
        self.refresh_aggregates()
        return self.conn.execute("SELECT day, source_org, n FROM facts_daily WHERE day > now() - INTERVAL '%s days' ORDER BY day" % int(days)).fetchall()
