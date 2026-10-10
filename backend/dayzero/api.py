"""FastAPI surface. Reads and writes go through PgStore. Every human action is audited."""
from __future__ import annotations

import json
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .coding import Coder
from .db import PgStore, connect
from .embed import get_embedder
from .extract import get_extractor
from .pipeline import Pipeline, confirm_field, merge_cases
from .schema import Message

load_dotenv()
app = FastAPI(title="Day Zero", version="0.1.0")
DATA = Path(__file__).resolve().parents[2] / "data"
_rsi = json.load(open(DATA / "mock_rsi.json"))["rsi"] if (DATA / "mock_rsi.json").exists() else {}
_coder = Coder() if (DATA / "mock_meddra.json").exists() else Coder(terms=[])


def store():
    return PgStore(connect())


@app.get("/api/health")
def health():
    return {"ok": True}


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
    from datetime import datetime, timezone
    from .schema import AuditEvent
    st.audit(AuditEvent(case_id=case_id, at=datetime.now(timezone.utc), actor=body.actor, action="duplicate_rejected", new=body.other_case_id))
    return {"ok": True}


@app.post("/api/messages")
def ingest(msg: Message):
    """Live intake: one raw report in, one assessed case out. Uses the configured extractor (oracle needs an answer key, so
    set DAYZERO_EXTRACTOR=claude for live demos)."""
    pipe = Pipeline(store(), get_extractor(answer_key={}), get_embedder(), _coder, _rsi)
    try:
        rec = pipe.process(msg)
    except KeyError:
        raise HTTPException(400, "oracle extractor has no answer for a new message; set DAYZERO_EXTRACTOR=claude")
    return rec.model_dump(mode="json")
