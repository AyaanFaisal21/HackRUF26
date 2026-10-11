import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api.js";
import { Org, Status, fmtDate, fmtDT } from "../components/ui.jsx";

export default function Documents() {
  const [rows, setRows] = useState([]); const [q, setQ] = useState(""); const [pid, setPid] = useState(""); const [hits, setHits] = useState(null);
  const [form, setForm] = useState({ patient_id: "", source_org: "Walk-in Clinic", kind: "clinic_note", document_date: "", text: "" }); const [result, setResult] = useState(null); const [busy, setBusy] = useState(false);
  const nav = useNavigate();
  useEffect(() => { api.documents().then(setRows); }, []);
  const search = () => api.search(q, pid || undefined).then(setHits);
  const ingest = () => { setBusy(true); setResult(null); api.ingest({ ...form, document_date: form.document_date || null }).then((r) => { setResult(r); api.documents().then(setRows); }).catch((e) => setResult({ error: e.message })).finally(() => setBusy(false)); };
  return (<>
    <h2 style={{ margin: "4px 0 2px" }}>Documents</h2>
    <div className="muted" style={{ marginBottom: 12 }}>Everything that arrived, kept unchanged. Each one was read into facts with receipts.</div>
    <div className="grid2">
      <div className="card">
        <h2>Find where a fact lives <span className="muted small">(vector search over every page)</span></h2>
        <div style={{ display: "flex", gap: 8 }}><input placeholder="e.g. most recent hemoglobin" value={q} onChange={(e) => setQ(e.target.value)} style={{ flex: 1 }} /><input placeholder="patient id (optional)" value={pid} onChange={(e) => setPid(e.target.value)} style={{ width: 160 }} /><button className="primary" onClick={search} disabled={!q}>search</button></div>
        {hits && <table style={{ marginTop: 8 }}><tbody>{hits.map((h, k) => <tr key={k}><td><Link to={`/documents/${h.document_id}`}>{h.document_id}</Link> <span className="muted small">p.{h.page} · {h.patient_id} · {h.kind}</span><div className="small muted" style={{ whiteSpace: "pre-wrap" }}>{h.text.slice(0, 220)}</div></td><td className="muted small">{Math.round(h.score * 100)}%</td></tr>)}</tbody></table>}
      </div>
      <div className="card">
        <h2>Ingest a document <span className="muted small">(live reading needs a model key)</span></h2>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <input placeholder="patient id" value={form.patient_id} onChange={(e) => setForm({ ...form, patient_id: e.target.value })} style={{ width: 150 }} />
          <input placeholder="source organization" value={form.source_org} onChange={(e) => setForm({ ...form, source_org: e.target.value })} style={{ width: 180 }} />
          <select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}>{["clinic_note", "lab_report", "discharge_summary", "pharmacy_list", "immunization_record", "other"].map((k) => <option key={k}>{k}</option>)}</select>
          <input type="date" value={form.document_date} onChange={(e) => setForm({ ...form, document_date: e.target.value })} />
        </div>
        <textarea placeholder="paste the document text (a fax, a note, a lab printout)" value={form.text} onChange={(e) => setForm({ ...form, text: e.target.value })} style={{ width: "100%", minHeight: 110, marginTop: 8 }} />
        <div style={{ marginTop: 8 }}><button className="primary" onClick={ingest} disabled={busy || !form.patient_id || !form.text}>{busy ? "reading…" : "store and read"}</button></div>
        {result && <div style={{ marginTop: 8 }}>{result.error ? <span className="pill red">{result.error}</span> : <span>Stored as <Link to={`/documents/${result.document_id}`}>{result.document_id}</Link> <Status s={result.status} /> {result.facts?.length ? `· ${result.facts.length} facts` : ""} {result.note && <span className="muted small">{result.note}</span>}</span>}</div>}
      </div>
    </div>
    <div className="card">
      <table><thead><tr><th>Document</th><th>Patient</th><th>From</th><th>Document date</th><th>Received</th><th>Status</th><th>Facts</th><th>Reader</th></tr></thead>
        <tbody>{rows.map((d) => (<tr key={d.id} className="row" onClick={() => nav(`/documents/${d.id}`)}>
          <td><b>{d.id}</b><div className="muted small">{d.kind.replace("_", " ")} · {d.n_pages} page{d.n_pages > 1 ? "s" : ""}</div></td><td>{d.patient_id}<div className="muted small">{d.display_name}</div></td><td><Org o={d.source_org} /></td><td>{fmtDate(d.document_date)}</td><td className="muted small">{fmtDT(d.received_at)}</td><td><Status s={d.status} /></td><td>{d.n_facts ?? ""}</td><td className="muted small">{d.reader}</td></tr>))}</tbody></table>
    </div>
  </>);
}
