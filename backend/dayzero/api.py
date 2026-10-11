"""FastAPI surface. Intake side (cases) and trial side (subjects, flags, briefs, forms). Every human action is recorded."""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import db_trials as T
from .brief import build_brief
from .coding import Coder
from .db import PgStore, connect
from .embed import get_embedder
from .extract import get_extractor
from .forms import form_from_case, form_from_subject
from .llm import provider
from .pipeline import Pipeline, confirm_field, merge_cases
from .schema import AuditEvent, Message

load_dotenv()
app = FastAPI(title="Day Zero", version="0.2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
DATA = Path(__file__).resolve().parents[2] / "data"
_rsi = json.load(open(DATA / "mock_rsi.json"))["rsi"] if (DATA / "mock_rsi.json").exists() else {}
_coder = Coder() if (DATA / "mock_meddra.json").exists() else Coder(terms=[])


def store():
    return PgStore(connect())


# ---------------- intake side
@app.get("/api/health")
def health():
    return {"ok": True, "llm": (provider().name if provider() else None)}


@app.get("/api/queue")
def queue():
    return store().queue()


@app.get("/api/stats")
def stats():
    return store().stats()


@app.get("/api/stats/intake")
def intake(days: int = 30):
    return store().intake_series(days)


@app.get("/api/cases/{case_id}")
def case(case_id: str):
    d = store().case_detail(case_id)
    if not d:
        raise HTTPException(404, case_id)
    return d


@app.get("/api/cases/{case_id}/history")
def history(case_id: str):
    return store().history(case_id)


class FieldDecision(BaseModel):
    field: str
    value: object
    actor: str = "reviewer"
    reason: str | None = None


@app.post("/api/cases/{case_id}/fields")
def decide_field(case_id: str, body: FieldDecision):
    try:
        rec = confirm_field(store(), case_id, body.field, body.value, body.actor, body.reason)
    except KeyError:
        raise HTTPException(404, case_id)
    return rec.model_dump(mode="json")


class MergeDecision(BaseModel):
    other_case_id: str
    merge: bool
    actor: str = "reviewer"


@app.post("/api/cases/{case_id}/duplicates")
def decide_duplicate(case_id: str, body: MergeDecision):
    st = store()
    st.conn.execute("UPDATE case_duplicates SET decided = %s WHERE (case_id = %s AND other_case_id = %s) OR (case_id = %s AND other_case_id = %s)",
                    ("merged" if body.merge else "not_duplicate", case_id, body.other_case_id, body.other_case_id, case_id))
    if body.merge:
        return merge_cases(st, case_id, body.other_case_id, body.actor, _coder, _rsi).model_dump(mode="json")
    st.audit(AuditEvent(case_id=case_id, at=datetime.now(timezone.utc), actor=body.actor, action="duplicate_rejected", new=body.other_case_id))
    return {"ok": True}


@app.post("/api/cases/{case_id}/form")
def case_form(case_id: str):
    """Create (or refresh) the pre-filled expedited report for an intake case."""
    st = store()
    rec = st.get_case(case_id)
    if not rec:
        raise HTTPException(404, case_id)
    r = T.upsert_form(st.conn, form_from_case(rec))
    return {"form_id": r["id"] if r else None}


@app.post("/api/messages")
def ingest(msg: Message):
    pipe = Pipeline(store(), get_extractor(answer_key={}), get_embedder(), _coder, _rsi)
    try:
        rec = pipe.process(msg)
    except KeyError:
        raise HTTPException(400, "oracle extractor has no answer for a new message; set DAYZERO_EXTRACTOR=model with a key")
    return rec.model_dump(mode="json")


# ---------------- trial side
@app.get("/api/trials")
def trials():
    return T.trials(connect())


@app.get("/api/trials/{trial_id}")
def trial(trial_id: str):
    d = T.trial_detail(connect(), trial_id)
    if not d:
        raise HTTPException(404, trial_id)
    return d


@app.get("/api/trials/{trial_id}/signals")
def trial_signals(trial_id: str):
    return T.signals(connect(), trial_id)


@app.get("/api/subjects/{subject_id}")
def subject(subject_id: str):
    p = T.subject_profile(connect(), subject_id)
    if not p:
        raise HTTPException(404, subject_id)
    return p


class FlagDecision(BaseModel):
    status: str          # confirmed | dismissed
    actor: str = "physician"


@app.post("/api/flags/{flag_id}")
def decide_flag(flag_id: str, body: FlagDecision):
    if body.status not in ("confirmed", "dismissed", "open"):
        raise HTTPException(400, "status must be confirmed, dismissed, or open")
    return T.decide_flag(connect(), flag_id, body.status, body.actor)


@app.post("/api/subjects/{subject_id}/brief")
def generate_brief(subject_id: str, narrative: bool = True):
    conn = connect()
    p = T.subject_profile(conn, subject_id)
    if not p:
        raise HTTPException(404, subject_id)
    rsi_terms = [t for lst in _rsi.values() for t in lst]
    body = build_brief(p, T.cohort_flags(conn, p["trial"]["id"]), rsi_terms, llm=provider() if narrative else None)
    r = T.save_brief(conn, subject_id, body)
    return {"brief_id": r["id"], "generated_at": r["generated_at"], "body": body}


class Assessment(BaseModel):
    physician: str
    relatedness: str                 # not_related | unlikely | possible | probable | definite
    serious: bool = False
    fatal: bool = False
    life_threatening: bool = False
    hospitalization: bool = False
    disability: bool = False
    other_medically_important: bool = False
    expected: bool = False
    dechallenge: str = "unknown"
    event: str = ""
    comment: str = ""


@app.post("/api/briefs/{brief_id}/sign")
def sign(brief_id: int, a: Assessment):
    conn = connect()
    assessment = {**a.model_dump(), "assessed_on": date.today().isoformat()}
    b = T.sign_brief(conn, brief_id, assessment, a.physician)
    if not b:
        raise HTTPException(404, str(brief_id))
    form_id = None
    if a.serious and not a.expected and a.relatedness in ("possible", "probable", "definite"):
        p = T.subject_profile(conn, b["subject_id"])
        r = T.upsert_form(conn, form_from_subject(p, b["body"], assessment))
        form_id = r["id"] if r else None
    return {"brief": b, "form_id": form_id}


@app.get("/api/fda")
def fda_queue():
    return T.forms(connect())


@app.get("/api/fda/{form_id}")
def fda_form(form_id: int):
    f = T.form(connect(), form_id)
    if not f:
        raise HTTPException(404, str(form_id))
    return f


class Verify(BaseModel):
    fields: list[str]
    actor: str = "provider"


@app.post("/api/fda/{form_id}/verify")
def fda_verify(form_id: int, v: Verify):
    return T.verify_form(connect(), form_id, v.fields, v.actor)


@app.post("/api/fda/{form_id}/submit")
def fda_submit(form_id: int):
    f = T.submit_form(connect(), form_id)
    if f["status"] != "submitted":
        raise HTTPException(409, "form must be fully verified before submission")
    return f
