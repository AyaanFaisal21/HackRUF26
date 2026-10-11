"""FastAPI surface for Sourced."""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .embed import get_embedder
from .forms import FORM_DEFS, FORMS, fill
from .llm import provider
from .reader import ModelDocReader, OracleDocReader, extraction_to_facts
from .schema import Document
from .store import Store, connect
from .verifier import verify

load_dotenv()
app = FastAPI(title="Sourced", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
ROOT = Path(__file__).resolve().parents[2]
_answer_key = None
_metrics_cache = {}


def store():
    return Store(connect())


def answer_key():
    global _answer_key
    if _answer_key is None:
        p = ROOT / "data/samples/world_answer_key.json"
        _answer_key = json.load(open(p)) if p.exists() else {"doc_extractions": {}, "planted": [], "visit_truth": {}, "children": []}
    return _answer_key


@app.get("/api/health")
def health():
    llm = provider()
    return {"ok": True, "model": f"{llm.name}:{llm.model}" if llm else None}


@app.get("/api/stats")
def stats():
    return store().stats()


@app.get("/api/stats/facts_daily")
def facts_daily(days: int = 400):
    return store().facts_daily(days)


@app.get("/api/patients")
def patients(q: str | None = None, kind: str | None = None):
    return store().patients(q, kind)


@app.get("/api/patients/{pid}")
def patient(pid: str):
    p = store().patient(pid)
    if not p:
        raise HTTPException(404, pid)
    return p


@app.get("/api/patients/{pid}/facts")
def patient_facts(pid: str, concept: str | None = None):
    return store().facts_for_patient(pid, concept)


@app.get("/api/documents")
def documents(status: str | None = None):
    return store().documents(status)


@app.get("/api/documents/{doc_id}")
def document(doc_id: str):
    d = store().document(doc_id)
    if not d:
        raise HTTPException(404, doc_id)
    return d


class Ingest(BaseModel):
    patient_id: str
    source_org: str
    kind: str = "clinic_note"
    document_date: date | None = None
    text: str


@app.post("/api/documents")
def ingest(body: Ingest):
    """Live intake of one document: store it, read it, write its facts with receipts."""
    st = store()
    did = f"DOC-U{hashlib.sha256(body.text.encode()).hexdigest()[:8].upper()}"
    doc = Document(id=did, patient_id=body.patient_id, source_org=body.source_org, kind=body.kind, received_at=datetime.now(timezone.utc), document_date=body.document_date, text=body.text, n_pages=body.text.count("\f") + 1)
    st.insert_document(doc, hashlib.sha256(body.text.encode()).hexdigest(), get_embedder())
    llm = provider()
    if llm is None:
        st.mark_document(did, "pending", None, None)
        return {"document_id": did, "status": "pending", "facts": [], "note": "no model key configured; document stored unread. Add ANTHROPIC_API_KEY or OPENAI_API_KEY to read live."}
    reader = ModelDocReader(llm)
    try:
        ext = reader.read(doc)
    except Exception as e:
        st.mark_document(did, "failed", reader.name, None)
        raise HTTPException(502, f"reader failed: {e}")
    facts, skipped = extraction_to_facts(doc, ext, reader.name)
    st.insert_facts(facts)
    st.mark_document(did, "read", reader.name, len(facts))
    st.audit("reader", "document_read", "document", did, None, None, {"facts": len(facts), "skipped": len(skipped)})
    return {"document_id": did, "status": "read", "facts": [f.model_dump(mode="json") for f in facts], "skipped": skipped}


@app.get("/api/search")
def search(q: str, patient_id: str | None = None, k: int = 8):
    return store().search_chunks(get_embedder().embed(q), k, patient_id)


@app.get("/api/forms")
def forms():
    return [f.model_dump() for f in FORM_DEFS]


class FillRequest(BaseModel):
    form_id: str
    visit_date: date
    second_opinion: bool = False


@app.post("/api/patients/{pid}/forms")
def fill_form(pid: str, body: FillRequest):
    if body.form_id not in FORMS:
        raise HTTPException(400, f"unknown form {body.form_id}")
    st = store()
    if not st.patient(pid):
        raise HTTPException(404, pid)
    inst = verify(fill(st, pid, FORMS[body.form_id], body.visit_date), FORMS[body.form_id], provider() if body.second_opinion else None)
    iid = st.save_instance(inst)
    st.audit("filler", "form_filled", "form_instance", iid, None, None, {"form": body.form_id, "visit": body.visit_date.isoformat(), "filled": inst.n_filled, "flagged": inst.n_flagged, "ms": inst.filled_ms})
    return st.instance(iid)


@app.get("/api/forms/instances/{iid}")
def instance(iid: int):
    i = store().instance(iid)
    if not i:
        raise HTTPException(404, str(iid))
    return i


class Decision(BaseModel):
    action: str            # accept | choose | manual | blank
    value: object = None
    fact_id: int | None = None
    actor: str = "reviewer"
    reason: str | None = None


@app.post("/api/forms/instances/{iid}/fields/{key}")
def decide(iid: int, key: str, d: Decision):
    if d.action not in ("accept", "choose", "manual", "blank"):
        raise HTTPException(400, "action must be accept, choose, manual, or blank")
    try:
        return store().decide_field(iid, key, {**d.model_dump(), "at": datetime.now(timezone.utc).isoformat()})
    except KeyError:
        raise HTTPException(404, key)


class Sign(BaseModel):
    actor: str


@app.post("/api/forms/instances/{iid}/sign")
def sign(iid: int, s: Sign):
    try:
        return store().sign(iid, s.actor)
    except ValueError as e:
        raise HTTPException(409, str(e))


@app.get("/api/forms/instances/{iid}/export")
def export(iid: int):
    i = store().instance(iid)
    if not i:
        raise HTTPException(404, str(iid))
    if not i["export"]:
        raise HTTPException(409, "form is not signed yet")
    return i["export"]


@app.get("/api/forms/instances/{iid}/history")
def form_history(iid: int):
    return store().history("form_instance", str(iid))


@app.get("/api/queue")
def queue():
    return store().queue()


@app.get("/api/metrics")
def metrics(refresh: bool = False, max_patients: int = 40):
    """Serves the metrics computed by `make eval` (data/samples/metrics.json); refresh=true recomputes against the live ledger."""
    from .evaluate import evaluate, reader_metrics
    from .generate import build_world
    saved = ROOT / "data/samples/metrics.json"
    if not refresh and saved.exists():
        return json.load(open(saved))
    key = f"{max_patients}"
    if refresh or key not in _metrics_cache:
        st = store()
        m = evaluate(st, answer_key(), st.patients(), max_patients)
        m["reader"] = reader_metrics(st, answer_key(), build_world(seed=7)["documents"])
        _metrics_cache[key] = {"computed_at": datetime.now(timezone.utc).isoformat(), **m}
    return _metrics_cache[key]
