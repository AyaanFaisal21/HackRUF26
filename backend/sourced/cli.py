"""python -m sourced.cli <command>. See the Makefile for the usual sequence."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from collections import Counter
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "data/samples"


def cmd_init_db(a):
    from .store import Store
    st = Store()
    if a.drop_legacy:
        st.drop_legacy(); print("legacy Day Zero tables dropped")
    st.init_schema(); print("schema applied")


def cmd_build_data(a):
    from .generate import build_world
    w = build_world(seed=a.seed, n_doc_adults=a.doc_adults, n_children=a.children)
    json.dump(w["truth"], open(SAMPLES / "world_answer_key.json", "w"))
    json.dump({"patients": w["patients"], "identifiers": w["identifiers"], "documents": w["documents"], "orgs": w["orgs"]}, open(SAMPLES / "world_documents.json", "w"), indent=1)
    print(f"patients {len(w['patients'])}  documents {len(w['documents'])}  planted {dict(Counter(p['kind'] for p in w['truth']['planted']))}")
    print(f"wrote {SAMPLES / 'world_answer_key.json'} and {SAMPLES / 'world_documents.json'}")


def cmd_load(a):
    from .embed import get_embedder
    from .forms import FORM_DEFS
    from .generate import build_world
    from .reader import ModelDocReader, OracleDocReader, extraction_to_facts, read_fhir_bundle
    from .schema import Document
    from .store import Store
    t0 = time.perf_counter()
    st = Store(); st.init_schema()
    if not a.keep:
        st.reset()
    w = build_world(seed=a.seed, n_doc_adults=a.doc_adults, n_children=a.children)
    json.dump(w["truth"], open(SAMPLES / "world_answer_key.json", "w"))
    st.insert_patients(w["patients"]); st.insert_identifiers(w["identifiers"])
    n_fhir = 0
    for p in w["patients"]:
        org = "Memorial General Hospital" if p["kind"] == "adult" else "Sunrise Pediatrics"
        n_fhir += st.insert_facts(read_fhir_bundle(w["bundles"][p["id"]], p["id"], org))
    cache_path = SAMPLES / "model_reads.json"
    cache = json.load(open(cache_path)) if (a.reader == "model" and cache_path.exists() and not a.no_cache) else {"reads": {}}
    docs = w["documents"][: a.max_docs] if a.max_docs else w["documents"]
    if a.reader == "oracle":
        reader = OracleDocReader(w["truth"]["doc_extractions"]); reader_name = "oracle"
    else:
        missing = [d for d in docs if d["sha256"] not in cache["reads"]]
        if missing:
            reader = ModelDocReader()          # needs a key; exits with a clear message otherwise
            reader_name = reader.name
            if cache.get("reader") not in (None, reader_name):
                cache = {"reads": {}}          # a different model: start a fresh cache
        else:
            reader, reader_name = None, cache.get("reader", "model (cached)")
            print(f"all {len(docs)} documents are in the read cache ({reader_name}); no model call needed")
    emb = get_embedder()
    n_doc = n_skipped = n_failed = n_cached = 0
    as_doc = lambda d: Document(id=d["id"], patient_id=d["patient_id"], source_org=d["source_org"], kind=d["kind"], received_at=datetime.fromisoformat(d["received_at"]), document_date=date.fromisoformat(d["document_date"]), text=d["text"], n_pages=d["n_pages"])
    def read_one(d):
        doc = as_doc(d)
        hit = cache["reads"].get(d["sha256"])
        if hit is not None:
            from .schema import DocExtraction
            return doc, DocExtraction.model_validate(hit), None, True
        try:
            return doc, reader.read(doc), None, False
        except Exception as e:
            return doc, None, e, False
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=a.workers if a.reader == "model" else 1) as ex:
        results = list(ex.map(read_one, docs))
    for (doc, ext, err, cached), d in zip(results, docs):
        st.insert_document(doc, d["sha256"], emb)
        if err is not None:
            n_failed += 1; st.mark_document(doc.id, "failed", reader_name, None); print(f"  {doc.id}: reader failed: {err}"); continue
        n_cached += cached
        if a.reader == "model" and not cached:
            cache["reads"][d["sha256"]] = ext.model_dump()
        try:
            facts, skipped = extraction_to_facts(doc, ext, reader_name + (" (cached)" if cached else ""), base_confidence=0.95 if a.reader == "oracle" else 0.85)
            n_doc += st.insert_facts(facts); n_skipped += len(skipped)
            st.mark_document(doc.id, "read", reader_name, len(facts))
        except Exception as e:
            n_failed += 1; st.mark_document(doc.id, "failed", reader_name, None); print(f"  {doc.id}: insert failed: {str(e)[:120]}")
    if a.reader == "model" and n_cached < len(docs) - n_failed:   # only rewrite the cache when new reads were added
        json.dump({"reader": reader_name, "updated": datetime.now().isoformat(timespec="seconds"), "reads": cache["reads"]}, open(cache_path, "w"))
    st.upsert_form_defs(FORM_DEFS); st.refresh_aggregates()
    st.audit("loader", "world_loaded", None, None, None, None, {"patients": len(w["patients"]), "fhir_facts": n_fhir, "document_facts": n_doc, "reader": a.reader})
    print(f"patients {len(w['patients'])} | FHIR facts {n_fhir} | documents {len(docs)} -> {n_doc} facts ({n_skipped} uncoded, {n_failed} failed, {n_cached} from cache) | reader={reader_name} | {time.perf_counter() - t0:.1f}s")


def cmd_fill(a):
    """Fill the standard visit forms for patients that have outside documents, so the queue has content."""
    from .forms import FORMS, fill
    from .store import Store
    from .verifier import verify
    st = Store()
    if a.reset:
        st.conn.execute("DELETE FROM form_instances")
    truth = json.load(open(SAMPLES / "world_answer_key.json"))
    pids = sorted({p["patient_id"] for p in truth["planted"]})
    adults = [p for p in pids if p.startswith("01-")][: a.patients]
    kids = [c["patient_id"] for c in truth["children"]]
    n = 0
    for pid in adults:
        vt = truth["visit_truth"].get(pid, {})
        visits = sorted({p["visit"] for p in truth["planted"] if p["patient_id"] == pid and p["concept"] != "medication"})
        for v in visits[: a.visits]:
            has = vt.get(v, {})
            for form_id in a.forms.split(","):
                if (form_id == "vs_visit" and "sbp" not in has) or (form_id == "lb_visit" and "alt" not in has):
                    continue   # nothing was collected for that page at this visit
                inst = verify(fill(st, pid, FORMS[form_id], date.fromisoformat(v)), FORMS[form_id])
                st.save_instance(inst); n += 1
    for pid in kids:
        st.save_instance(verify(fill(st, pid, FORMS["nj_ch14"], date.today()), FORMS["nj_ch14"])); n += 1
    print(f"filled {n} forms for {len(adults)} adults and {len(kids)} children")


def cmd_evaluate(a):
    from .evaluate import evaluate, to_markdown
    from .store import Store
    from .evaluate import reader_metrics
    from .generate import build_world
    st = Store()
    truth = json.load(open(SAMPLES / "world_answer_key.json"))
    m = evaluate(st, truth, st.patients(), a.patients)
    m["reader"] = reader_metrics(st, truth, build_world(seed=a.seed)["documents"])
    md = to_markdown(m, a.reader)
    print(md)
    if a.out:
        Path(a.out).write_text(md + "\n"); print(f"\nwrote {a.out}")


def cmd_compress(a):
    from .store import Store
    st = Store()
    n = st.conn.execute("SELECT count(compress_chunk(c, true)) AS n FROM show_chunks('facts', older_than => INTERVAL '%s days') c" % int(a.days)).fetchone()["n"]
    s = st.conn.execute("SELECT * FROM hypertable_compression_stats('facts')").fetchone()
    print(f"compressed {n} chunks; {s['number_compressed_chunks']}/{s['total_chunks']} chunks compressed; {s['before_compression_total_bytes'] / 1e6:.1f} MB -> {s['after_compression_total_bytes'] / 1e6:.1f} MB")


def main():
    p = argparse.ArgumentParser(prog="sourced"); sub = p.add_subparsers(required=True)
    s = sub.add_parser("init-db"); s.add_argument("--drop-legacy", action="store_true"); s.set_defaults(f=cmd_init_db)
    s = sub.add_parser("build-data"); s.add_argument("--seed", type=int, default=7); s.add_argument("--doc-adults", type=int, default=80); s.add_argument("--children", type=int, default=10); s.set_defaults(f=cmd_build_data)
    s = sub.add_parser("load"); s.add_argument("--seed", type=int, default=7); s.add_argument("--doc-adults", type=int, default=80); s.add_argument("--children", type=int, default=10)
    s.add_argument("--reader", choices=["oracle", "model"], default=os.environ.get("SOURCED_READER", "oracle")); s.add_argument("--max-docs", type=int, default=0); s.add_argument("--workers", type=int, default=6); s.add_argument("--keep", action="store_true"); s.add_argument("--no-cache", action="store_true", help="call the model even when a cached read exists"); s.set_defaults(f=cmd_load)
    s = sub.add_parser("fill"); s.add_argument("--patients", type=int, default=30); s.add_argument("--visits", type=int, default=2); s.add_argument("--forms", default="vs_visit,lb_visit,cm_log"); s.add_argument("--reset", action="store_true", help="delete existing form instances first"); s.set_defaults(f=cmd_fill)
    s = sub.add_parser("evaluate"); s.add_argument("--patients", type=int, default=60); s.add_argument("--seed", type=int, default=7); s.add_argument("--reader", default=os.environ.get("SOURCED_READER", "oracle")); s.add_argument("--out", default=None); s.set_defaults(f=cmd_evaluate)
    s = sub.add_parser("compress"); s.add_argument("--days", type=int, default=120); s.set_defaults(f=cmd_compress)
    a = p.parse_args(); a.f(a)


if __name__ == "__main__":
    main()
