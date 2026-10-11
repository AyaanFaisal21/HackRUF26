"""Tiger Data access for the trial side. Bulk loads use COPY; reads are shaped for the API."""
from __future__ import annotations

import io
import json
from datetime import date, datetime, timezone
from pathlib import Path

from psycopg.types.json import Jsonb as _Jsonb


def Jsonb(obj):
    """psycopg's Jsonb with dates and datetimes rendered as ISO strings."""
    return _Jsonb(json.loads(json.dumps(obj, default=str)))

SQL_DIR = Path(__file__).resolve().parents[1] / "sql"


def init_trial_schema(conn):
    conn.execute(open(SQL_DIR / "trial_schema.sql").read())


def reset_trial(conn, trial_id: str):
    # compressed chunks cannot be bulk-deleted under the default decompression limit; decompress first, policy recompresses later
    conn.execute("SET timescaledb.max_tuples_decompressed_per_dml_transaction = 0")
    conn.execute("SELECT decompress_chunk(c, true) FROM show_chunks('diary_entries') c")
    for t in ("fda_forms", "briefs", "flags", "subject_events", "lab_results", "diary_entries"):
        if t == "fda_forms":
            conn.execute("DELETE FROM fda_forms WHERE source_type = 'trial_subject'")
        else:
            conn.execute(f"DELETE FROM {t} WHERE {'trial_id' if t == 'flags' else 'subject_id'} {'= %s' if t == 'flags' else 'IN (SELECT id FROM subjects WHERE trial_id = %s)'}", (trial_id,))
    conn.execute("DELETE FROM subjects WHERE trial_id = %s", (trial_id,))
    conn.execute("DELETE FROM trials WHERE id = %s", (trial_id,))


def _copy(conn, table, cols, rows):
    buf = io.StringIO()
    for r in rows:
        buf.write("\t".join("\\N" if v is None else str(v).replace("\t", " ").replace("\n", " ") for v in r) + "\n")
    buf.seek(0)
    with conn.cursor() as cur, cur.copy(f"COPY {table} ({', '.join(cols)}) FROM STDIN") as cp:
        cp.write(buf.read())


def load_bundle(conn, bundle: dict):
    from .trials import day_to_date
    t = bundle["trial"]["trial"]
    reset_trial(conn, t["id"])
    conn.execute("INSERT INTO trials (id, name, product, phase, sites, source) VALUES (%s,%s,%s,%s,%s,%s)", (t["id"], t["name"], t["product"], t["phase"], t["sites"], t.get("source")))
    subj = {s["id"]: s for s in bundle["trial"]["subjects"]}
    _copy(conn, "subjects", ["id", "trial_id", "site", "age", "sex", "race", "ref_date", "last_day"],
          [(s["id"], t["id"], s["site"], s["age"], s["sex"], s.get("race"), s["ref_date"], s["last_day"]) for s in subj.values()])
    _copy(conn, "diary_entries", ["subject_id", "entry_date", "study_day", "item", "grade"],
          [(d["subject"], d["date"], d["day"], d["item"], d["grade"]) for d in bundle["diaries"]])
    seen = set()
    labs = []
    for r in bundle["trial"]["labs"]:
        key = (r["subject"], r["day"], r["test"], r["visit"])
        if key in seen:
            continue
        seen.add(key)
        labs.append((r["subject"], day_to_date(subj[r["subject"]], r["day"]).isoformat(), r["day"], r["test"], r["value"], r["lln"], r["uln"], r["unit"], r["visit"], round(r["value"] / r["uln"], 3) if r["uln"] else None))
    _copy(conn, "lab_results", ["subject_id", "result_date", "study_day", "test", "value", "lln", "uln", "unit", "visit", "x_uln"], labs)
    _copy(conn, "subject_events", ["subject_id", "term", "pt", "soc", "start_day", "end_day", "severity", "serious"],
          [(e["subject"], e["term"], e["pt"], e["soc"], e["start_day"], e["end_day"], e["severity"], e["serious"]) for e in bundle["trial"]["events"]])
    for f in bundle["flags"]:
        conn.execute("""INSERT INTO flags (id, trial_id, subject_id, site, rule, severity, fired_on, study_day, title, citation, logic, evidence, status)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'open')""",
                     (f["id"], f["trial"], f["subject"], f["site"], f["rule"], f["severity"], f["fired_on"], f["day"], f["title"], f["citation"], Jsonb(f["logic"]), Jsonb(f["evidence"])))
    refresh_weekly(conn)


def refresh_weekly(conn):
    """Best effort: the refresh policy may already hold the lock, in which case it is doing the work for us."""
    import psycopg
    try:
        conn.execute("CALL refresh_continuous_aggregate('diary_weekly', NULL, NULL)")
    except psycopg.errors.LockNotAvailable:
        pass


# ---- reads
def trials(conn):
    return conn.execute("""SELECT t.*, (SELECT count(*) FROM subjects s WHERE s.trial_id = t.id) AS n_subjects,
                                  (SELECT count(*) FROM flags f WHERE f.trial_id = t.id AND f.status = 'open') AS open_flags,
                                  (SELECT count(*) FROM flags f WHERE f.trial_id = t.id AND f.status = 'open' AND f.severity = 'urgent') AS urgent_flags,
                                  (SELECT count(*) FROM fda_forms WHERE status = 'draft') AS forms_pending
                           FROM trials t ORDER BY id""").fetchall()


def trial_detail(conn, trial_id):
    t = conn.execute("SELECT * FROM trials WHERE id = %s", (trial_id,)).fetchone()
    if not t:
        return None
    subs = conn.execute("""SELECT s.*, (SELECT count(*) FROM flags f WHERE f.subject_id = s.id AND f.status = 'open') AS open_flags,
                                  (SELECT max(CASE severity WHEN 'urgent' THEN 3 WHEN 'review' THEN 2 ELSE 1 END) FROM flags f WHERE f.subject_id = s.id AND f.status = 'open') AS top_severity,
                                  (SELECT max(entry_date) FROM diary_entries d WHERE d.subject_id = s.id) AS last_diary,
                                  (SELECT x_uln FROM lab_results l WHERE l.subject_id = s.id AND l.test = 'ALT' ORDER BY result_date DESC LIMIT 1) AS latest_alt_x_uln,
                                  (SELECT round(avg(grade)::numeric, 2) FROM diary_entries d WHERE d.subject_id = s.id AND d.entry_date > CURRENT_DATE - 7) AS symptom_burden_7d
                           FROM subjects s WHERE s.trial_id = %s ORDER BY top_severity DESC NULLS LAST, open_flags DESC, s.id""", (trial_id,)).fetchall()
    site_flags = conn.execute("SELECT * FROM flags WHERE trial_id = %s AND subject_id IS NULL ORDER BY severity", (trial_id,)).fetchall()
    return {"trial": t, "subjects": subs, "site_flags": site_flags}


def subject_profile(conn, subject_id):
    s = conn.execute("SELECT s.*, t.product, t.name AS trial_name FROM subjects s JOIN trials t ON t.id = s.trial_id WHERE s.id = %s", (subject_id,)).fetchone()
    if not s:
        return None
    diaries = conn.execute("SELECT entry_date AS date, study_day AS day, item, grade FROM diary_entries WHERE subject_id = %s ORDER BY entry_date", (subject_id,)).fetchall()
    labs = conn.execute("SELECT result_date AS date, study_day AS day, test, value, uln, unit, visit, x_uln FROM lab_results WHERE subject_id = %s ORDER BY result_date", (subject_id,)).fetchall()
    events = conn.execute("SELECT term, pt, soc, start_day, end_day, severity, serious FROM subject_events WHERE subject_id = %s ORDER BY start_day NULLS LAST", (subject_id,)).fetchall()
    flags = conn.execute("SELECT * FROM flags WHERE subject_id = %s ORDER BY fired_on DESC", (subject_id,)).fetchall()
    briefs = conn.execute("SELECT id, generated_at, assessment, signed_by, signed_at, body FROM briefs WHERE subject_id = %s ORDER BY generated_at DESC", (subject_id,)).fetchall()
    forms = conn.execute("SELECT id, status, due_date, clock_days FROM fda_forms WHERE source_type = 'trial_subject' AND source_id = %s", (subject_id,)).fetchall()
    return {"subject": s, "trial": {"id": s["trial_id"], "product": s["product"], "name": s["trial_name"]}, "diaries": diaries, "labs": labs, "events": events, "flags": flags, "briefs": briefs, "forms": forms}


def cohort_flags(conn, trial_id):
    return conn.execute("SELECT id, subject_id, rule, severity, title FROM flags WHERE trial_id = %s AND status <> 'dismissed'", (trial_id,)).fetchall()


def decide_flag(conn, flag_id, status, actor):
    conn.execute("UPDATE flags SET status = %s, decided_by = %s, decided_at = now() WHERE id = %s", (status, actor, flag_id))
    return conn.execute("SELECT * FROM flags WHERE id = %s", (flag_id,)).fetchone()


def save_brief(conn, subject_id, body):
    return conn.execute("INSERT INTO briefs (subject_id, body) VALUES (%s, %s) RETURNING id, generated_at", (subject_id, Jsonb(body))).fetchone()


def sign_brief(conn, brief_id, assessment, physician):
    conn.execute("UPDATE briefs SET assessment = %s, signed_by = %s, signed_at = now() WHERE id = %s", (Jsonb(assessment), physician, brief_id))
    return conn.execute("SELECT * FROM briefs WHERE id = %s", (brief_id,)).fetchone()


def upsert_form(conn, form: dict):
    return conn.execute("""INSERT INTO fda_forms (source_type, source_id, status, due_date, clock_days, body)
                           VALUES (%s,%s,'draft',%s,%s,%s)
                           ON CONFLICT (source_type, source_id) DO UPDATE SET body = EXCLUDED.body, due_date = EXCLUDED.due_date, clock_days = EXCLUDED.clock_days
                           WHERE fda_forms.status = 'draft' RETURNING id""",
                        (form["source_type"], form["source_id"], form.get("due_date"), form.get("clock_days"), Jsonb(form))).fetchone()


def forms(conn):
    return conn.execute("""SELECT id, created_at, source_type, source_id, status, due_date, clock_days, verified_by, submitted_at,
                                  body->>'reactions' AS reactions, (due_date - CURRENT_DATE) AS days_left
                           FROM fda_forms ORDER BY (status <> 'draft'), (due_date IS NULL), due_date""").fetchall()


def form(conn, form_id):
    return conn.execute("SELECT * FROM fda_forms WHERE id = %s", (form_id,)).fetchone()


def verify_form(conn, form_id, fields, actor):
    r = conn.execute("SELECT body FROM fda_forms WHERE id = %s", (form_id,)).fetchone()
    body = r["body"]; body["verified_fields"] = sorted(set(body.get("verified_fields", [])) | set(fields)); body["signed_by"] = actor
    total = sum(len(v) for v in body["sections"].values())
    status = "verified" if len(body["verified_fields"]) >= total else "draft"
    conn.execute("UPDATE fda_forms SET body = %s, status = %s, verified_by = %s, verified_at = CASE WHEN %s = 'verified' THEN now() ELSE verified_at END WHERE id = %s",
                 (Jsonb(body), status, actor, status, form_id))
    return conn.execute("SELECT * FROM fda_forms WHERE id = %s", (form_id,)).fetchone()


def submit_form(conn, form_id):
    conn.execute("UPDATE fda_forms SET status = 'submitted', submitted_at = now() WHERE id = %s AND status = 'verified'", (form_id,))
    return conn.execute("SELECT * FROM fda_forms WHERE id = %s", (form_id,)).fetchone()


def signals(conn, trial_id):
    refresh_weekly(conn)
    weekly = conn.execute("SELECT week, item, mean_grade, n_severe, n_subjects FROM diary_weekly ORDER BY week, item").fetchall()
    rules = conn.execute("SELECT rule, severity, count(*) AS n, count(*) FILTER (WHERE status='open') AS open FROM flags WHERE trial_id = %s GROUP BY rule, severity ORDER BY n DESC", (trial_id,)).fetchall()
    events = conn.execute("""SELECT pt, count(*) AS n, count(*) FILTER (WHERE serious) AS serious FROM subject_events e JOIN subjects s ON s.id = e.subject_id
                             WHERE s.trial_id = %s GROUP BY pt ORDER BY n DESC LIMIT 15""", (trial_id,)).fetchall()
    return {"diary_weekly": weekly, "flag_rules": rules, "top_events": events}
