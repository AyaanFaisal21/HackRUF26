"""python -m dayzero.cli <command>. See Makefile for the usual sequence."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from .schema import Message

load_dotenv()
ROOT = Path(__file__).resolve().parents[2]


def _load_faers(path):
    p = Path(path)
    files = [p] if p.is_file() else sorted(p.glob("faers*.json"))
    recs = []
    for f in files:
        recs += json.load(open(f)).get("results", [])
    if not recs:
        raise SystemExit(f"no FAERS records under {path}; run `make fetch` first")
    return recs


def cmd_fetch(a):
    import requests
    out, recs = Path(a.out), []
    for skip in range(0, a.n, 100):
        r = requests.get("https://api.fda.gov/drug/event.json", params={"search": f"receivedate:[{a.since}+TO+{a.until}]+AND+serious:1", "limit": min(100, a.n - skip), "skip": skip}, timeout=60)
        r.raise_for_status()
        recs += r.json()["results"]
    out.parent.mkdir(parents=True, exist_ok=True)
    json.dump({"source": "openFDA drug/event", "results": recs}, open(out, "w"))
    print(f"wrote {len(recs)} records to {out}")


def cmd_mock(a):
    from .generate import build_mock_data
    meddra, rsi = build_mock_data(_load_faers(a.faers))
    json.dump(meddra, open(ROOT / "data/mock_meddra.json", "w"), indent=1)
    json.dump(rsi, open(ROOT / "data/mock_rsi.json", "w"), indent=1)
    print(f"mock MedDRA terms: {len(meddra['terms'])}  products with mock RSI: {len(rsi['rsi'])}")


def cmd_inbox(a):
    from .generate import build_inbox
    msgs, key = build_inbox(_load_faers(a.faers), n=a.n, seed=a.seed, days=a.days)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    json.dump(msgs, open(out / "inbox.json", "w"), indent=1)
    json.dump(key, open(out / "answer_key.json", "w"), indent=1)
    from collections import Counter
    print(f"wrote {len(msgs)} messages; variants: {dict(Counter(v['variant'] for v in key.values()))}")


def _pipeline(store, answer_key):
    from .coding import Coder
    from .embed import get_embedder
    from .extract import get_extractor
    from .pipeline import Pipeline
    rsi = json.load(open(ROOT / "data/mock_rsi.json"))["rsi"] if (ROOT / "data/mock_rsi.json").exists() else {}
    return Pipeline(store, get_extractor(answer_key), get_embedder(), Coder(), rsi)


def _messages(path):
    return [Message.model_validate(m) for m in json.load(open(path))]


def cmd_init_db(a):
    from .db import connect, init_schema
    from .db_trials import init_trial_schema
    conn = connect(); init_schema(conn); init_trial_schema(conn); print("schema applied")


def cmd_load(a):
    from .db import PgStore, connect, init_schema
    from .db_trials import init_trial_schema, upsert_form
    from .forms import form_from_case
    conn = connect(); init_schema(conn); init_trial_schema(conn)
    if not a.keep:
        for t in ("case_duplicates", "case_audit", "case_reactions", "case_drugs", "cases", "message_embeddings", "messages"):
            conn.execute(f"DELETE FROM {t}")
        conn.execute("DELETE FROM fda_forms WHERE source_type = 'intake_case'")
    key = json.load(open(a.answer_key)) if a.answer_key else None
    pipe = _pipeline(PgStore(conn), key)
    recs = pipe.process_many(_messages(a.inbox))
    n_forms = 0
    for rec in recs:
        if rec.assessment.expedited and rec.merged_into is None:
            upsert_form(conn, form_from_case(rec)); n_forms += 1
    print(f"loaded {len(recs)} messages into the database; {n_forms} expedited report drafts queued; extractor={os.environ.get('DAYZERO_EXTRACTOR', 'oracle')}")


def cmd_load_trial(a):
    from .db import connect
    from .db_trials import init_trial_schema, load_bundle
    from .trials import build_trial_bundle
    conn = connect(); init_trial_schema(conn)
    bundle = build_trial_bundle(seed=a.seed)
    load_bundle(conn, bundle)
    json.dump(bundle["truth"], open(ROOT / "data/samples/trial_answer_key.json", "w"), indent=1)
    from collections import Counter
    print(f"trial {bundle['trial']['trial']['id']}: {len(bundle['trial']['subjects'])} subjects, {len(bundle['diaries'])} diary rows, {len(bundle['trial']['labs'])} lab rows, "
          f"{len(bundle['flags'])} flags {dict(Counter(f['rule'] for f in bundle['flags']))}; planted {len(bundle['truth'])} (answer key written)")


def cmd_evaluate(a):
    from .coding import Coder
    from .evaluate import evaluate, to_markdown
    from .pipeline import MemoryStore
    key = json.load(open(a.answer_key))
    store = MemoryStore()
    pipe = _pipeline(store, key)
    pipe.process_many(_messages(a.inbox))
    m = evaluate(store, key, Coder())
    md = to_markdown(m, os.environ.get("DAYZERO_EXTRACTOR", "oracle"))
    print(md)
    if a.out:
        Path(a.out).write_text(md + "\n"); print(f"\nwrote {a.out}")


def main():
    p = argparse.ArgumentParser(prog="dayzero"); sub = p.add_subparsers(required=True)
    s = sub.add_parser("fetch"); s.add_argument("--n", type=int, default=300); s.add_argument("--since", default="20240101"); s.add_argument("--until", default="20241231"); s.add_argument("--out", default="data/raw/faers.json"); s.set_defaults(f=cmd_fetch)
    s = sub.add_parser("build-mock-data"); s.add_argument("--faers", default="data/raw"); s.set_defaults(f=cmd_mock)
    s = sub.add_parser("build-inbox"); s.add_argument("--faers", default="data/raw"); s.add_argument("--n", type=int, default=60); s.add_argument("--seed", type=int, default=7); s.add_argument("--days", type=int, default=12); s.add_argument("--out", default="data/samples"); s.set_defaults(f=cmd_inbox)
    s = sub.add_parser("init-db"); s.set_defaults(f=cmd_init_db)
    s = sub.add_parser("load"); s.add_argument("--inbox", default="data/samples/inbox.json"); s.add_argument("--answer-key", default="data/samples/answer_key.json"); s.add_argument("--keep", action="store_true", help="append instead of resetting intake tables"); s.set_defaults(f=cmd_load)
    s = sub.add_parser("load-trial"); s.add_argument("--seed", type=int, default=7); s.set_defaults(f=cmd_load_trial)
    s = sub.add_parser("evaluate"); s.add_argument("--inbox", default="data/samples/inbox.json"); s.add_argument("--answer-key", default="data/samples/answer_key.json"); s.add_argument("--out", default=None); s.set_defaults(f=cmd_evaluate)
    a = p.parse_args(); a.f(a)


if __name__ == "__main__":
    main()
