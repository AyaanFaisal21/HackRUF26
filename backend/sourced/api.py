"""FastAPI surface for Sourced."""
from __future__ import annotations

import hashlib
import json
import mimetypes
from datetime import date, datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .embed import get_embedder
from .forms import FORM_DEFS, FORMS, fill
from .llm import provider
from .reader import ModelDocReader, OracleDocReader, extraction_to_facts, parse_date
from .schema import Document, Suggestion
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


KINDS = ("lab_report", "clinic_note", "discharge_summary", "pharmacy_list", "immunization_record", "urgent_care_note", "other")


def _norm_kind(k: str | None) -> str:
    """The reader's free-text document kind ('Clinic note') onto our vocabulary."""
    k = (k or "").strip().lower().replace("-", " ").replace("_", " ")
    for known in KINDS:
        if known.replace("_", " ") == k:
            return known
    for known in KINDS:
        if known.split("_")[0] in k:
            return known
    return "other"


def _ingest(st, patient_id: str, source_org: str, kind: str | None, document_date, text: str, image: bytes | None = None, image_type: str | None = None, transcribed: bool = False):
    """Live intake of one document: store it unchanged, read it, write its facts with receipts.
    kind 'auto' lets the reader say what the document is; a missing date is taken from the document."""
    raw = image if image is not None else text.encode()
    sha = hashlib.sha256(raw).hexdigest()
    did = f"DOC-U{sha[:8].upper()}"
    if st.conn.execute("SELECT 1 FROM documents WHERE id = %s", (did,)).fetchone():
        raise HTTPException(409, f"this exact document is already stored as {did}")
    auto = kind in (None, "", "auto")
    doc = Document(id=did, patient_id=patient_id, source_org=source_org, kind="other" if auto else kind, received_at=datetime.now(timezone.utc), document_date=document_date, text=text, n_pages=text.count("\f") + 1)
    st.insert_document(doc, sha, get_embedder(), image=image, image_type=image_type)
    llm = provider()
    if llm is None:
        st.mark_document(did, "pending", None, None)
        return {"document_id": did, "status": "pending", "facts": [], "transcribed": transcribed, "note": "no model key configured; document stored unread. Add ANTHROPIC_API_KEY or OPENAI_API_KEY to read live."}
    reader = ModelDocReader(llm)
    try:
        ext = reader.read(doc)
    except Exception as e:
        st.mark_document(did, "failed", reader.name, None)
        raise HTTPException(502, f"reader failed: {e}")
    new_kind = _norm_kind(ext.document_kind) if auto else None
    new_date = parse_date(ext.document_date) if (document_date is None and ext.document_date) else None
    if new_kind or new_date:
        st.set_document_meta(did, new_kind, new_date)
        doc.kind = new_kind or doc.kind
        doc.document_date = doc.document_date or new_date
    facts, skipped = extraction_to_facts(doc, ext, reader.name)
    st.insert_facts(facts)
    st.mark_document(did, "read", reader.name, len(facts))
    st.audit("reader", "document_read", "document", did, None, None, {"facts": len(facts), "skipped": len(skipped), "transcribed": transcribed, "kind": doc.kind})
    return {"document_id": did, "status": "read", "kind": doc.kind, "document_date": doc.document_date, "patient_name": ext.patient_name, "facts": [f.model_dump(mode="json") for f in facts], "skipped": skipped, "transcribed": transcribed, "text": text if transcribed else None}


@app.post("/api/documents")
def ingest(body: Ingest):
    """Text intake: a pasted fax or note, or what a fax server or EHR export would post here."""
    return _ingest(store(), body.patient_id, body.source_org, body.kind, body.document_date, body.text)


@app.post("/api/documents/upload")
async def upload(file: UploadFile = File(...), patient_id: str = Form(...), source_org: str = Form(...), kind: str = Form("auto"), document_date: str = Form("")):
    """Photo, scan, or PDF intake. Images and scanned pages are transcribed by the model, then read like any text;
    the receipts point into the transcription and the original is kept beside it."""
    data = await file.read()
    mt = (file.content_type or mimetypes.guess_type(file.filename or "")[0] or "application/octet-stream").split(";")[0].strip()
    dd = date.fromisoformat(document_date) if document_date else None
    st = store()
    if mt.startswith("text/"):
        return _ingest(st, patient_id, source_org, kind, dd, data.decode(errors="replace"))
    images: list[tuple[bytes, str]] = []
    page_texts: list[str | None] = []
    if mt == "application/pdf":
        import pymupdf
        pdf = pymupdf.open(stream=data, filetype="pdf")
        for page in pdf:
            t = page.get_text()
            if len(t.strip()) > 80:
                page_texts.append(t)
            else:
                page_texts.append(None)
                images.append((page.get_pixmap(dpi=150).tobytes("png"), "image/png"))
    elif mt.startswith("image/"):
        images.append((data, mt))
    else:
        raise HTTPException(415, f"unsupported type {mt}; send an image, a PDF, or text")
    transcribed = False
    if images:
        llm = provider()
        if llm is None:
            raise HTTPException(409, "transcribing a photo or scan needs a model key (OPENAI_API_KEY or ANTHROPIC_API_KEY)")
        try:
            t = llm.transcribe(images)
        except Exception as e:
            raise HTTPException(502, f"transcription failed: {e}")
        transcribed = True
        if mt == "application/pdf":
            it = iter(t.split("\f"))
            text = "\f".join(pt if pt is not None else next(it, "") for pt in page_texts)
        else:
            text = t
    else:
        text = "\f".join(p or "" for p in page_texts)
    if not text.strip():
        raise HTTPException(422, "nothing readable in the file")
    return _ingest(st, patient_id, source_org, kind, dd, text, image=data, image_type=mt, transcribed=transcribed)


@app.get("/api/documents/{doc_id}/image")
def document_image(doc_id: str):
    r = store().document_image(doc_id)
    if not r:
        raise HTTPException(404, doc_id)
    return Response(content=bytes(r["image"]), media_type=r["image_type"] or "application/octet-stream")


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
    inst = verify(fill(st, pid, FORMS[body.form_id], body.visit_date), FORMS[body.form_id], provider() if body.second_opinion else None, store=st)
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


@app.post("/api/forms/instances/{iid}/fields/{key}/explain")
def explain(iid: int, key: str):
    """Ask the model to explain a flagged field using only the receipts already on the field. The answer is stored on the field."""
    st = store()
    f = st.conn.execute("SELECT * FROM form_fields WHERE instance_id = %s AND key = %s", (iid, key)).fetchone()
    if not f:
        raise HTTPException(404, key)
    llm = provider()
    if llm is None:
        raise HTTPException(409, "no model key configured")
    rows = [{k: v for k, v in r.items() if k != "values"} for r in (f["rows"] or []) if r.get("conflicts")]
    kinds = st.document_kinds([s.get("document_id") for r in rows for s in r.get("sources", [])] + [((f["receipt"] or {}).get("document_id"))] + [a["receipt"].get("document_id") for a in (f["alternatives"] or [])])
    facts = {"field": f["label"], "value": f["value"], "unit": f["unit"], "receipt": f["receipt"], "alternatives": f["alternatives"], "verifier": f["verifier"], "rows": rows, "document_kinds": kinds}
    sug = llm.parse("You advise a study coordinator on one flagged field of a clinical trial form. Use only the facts in the JSON: sources, document kinds, pages, quotes, dates, values, "
                    "and the rule-based diagnosis if present. Do not invent facts. A dispensing list cannot show a stop; a structured record with an end date can. "
                    "Say what most likely happened, how sure the receipts let you be, what to record, and what to verify before signing.",
                    json.dumps(facts, default=str), Suggestion)
    verifier = {**(f["verifier"] or {}), "model_suggestion": sug.model_dump(), "model": f"{llm.name}:{llm.model}"}
    text = sug.likely_cause
    from .store import J
    st.conn.execute("UPDATE form_fields SET verifier = %s WHERE instance_id = %s AND key = %s", (J(verifier), iid, key))
    st.audit("model", "field_explained", "form_instance", iid, key, None, {"model": verifier["model"]})
    return {"suggestion": sug.model_dump(), "model": verifier["model"]}


@app.get("/api/forms/instances/{iid}/export")
def export(iid: int):
    i = store().instance(iid)
    if not i:
        raise HTTPException(404, str(iid))
    if not i["export"]:
        raise HTTPException(409, "form is not signed yet")
    return i["export"]


@app.get("/api/audit/verify")
def audit_verify():
    """Recompute the whole hash chain. intact=false names the first event whose link does not hold."""
    return store().verify_audit()


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
