import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api.js";
import { Kind, Org, Status, fmtDate, fmtDT } from "../components/ui.jsx";

export default function Documents() {
  const [rows, setRows] = useState([]); const [q, setQ] = useState(""); const [pid, setPid] = useState(""); const [hits, setHits] = useState(null);
  const [form, setForm] = useState({ patient_id: "", source_org: "Walk-in Clinic", kind: "auto", document_date: "", text: "" }); const [result, setResult] = useState(null); const [busy, setBusy] = useState(false); const [file, setFile] = useState(null);
  const nav = useNavigate();
  useEffect(() => { api.documents().then(setRows); }, []);
  const search = () => api.search(q, pid || undefined).then(setHits);
  const ingest = () => { setBusy(true); setResult(null); api.ingest({ ...form, document_date: form.document_date || null }).then((r) => { setResult(r); api.documents().then(setRows); }).catch((e) => setResult({ error: e.message })).finally(() => setBusy(false)); };
  const upload = () => { const fd = new FormData(); fd.append("file", file); fd.append("patient_id", form.patient_id); fd.append("source_org", form.source_org); fd.append("kind", form.kind); fd.append("document_date", form.document_date || "");
    setBusy(true); setResult(null); api.upload(fd).then((r) => { setResult(r); setFile(null); api.documents().then(setRows); }).catch((e) => setResult({ error: e.message })).finally(() => setBusy(false)); };
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
        <h2>Ingest a document <span className="muted small">(a fax server, scanner, or EHR export would post here; live reading needs a model key)</span></h2>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <input placeholder="patient id" value={form.patient_id} onChange={(e) => setForm({ ...form, patient_id: e.target.value })} style={{ width: 150 }} />
          <input placeholder="source organization" value={form.source_org} onChange={(e) => setForm({ ...form, source_org: e.target.value })} style={{ width: 180 }} />
          <select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}>{["auto", "clinic_note", "lab_report", "discharge_summary", "pharmacy_list", "immunization_record", "urgent_care_note", "other"].map((k) => <option key={k} value={k}>{k === "auto" ? "kind: let the reader decide" : k}</option>)}</select>
          <input type="date" value={form.document_date} onChange={(e) => setForm({ ...form, document_date: e.target.value })} />
        </div>
        <textarea placeholder="paste the document text (a fax, a note, a lab printout)" value={form.text} onChange={(e) => setForm({ ...form, text: e.target.value })} style={{ width: "100%", minHeight: 110, marginTop: 8 }} />
        <div style={{ marginTop: 8, display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <button className="primary" onClick={ingest} disabled={busy || !form.patient_id || !form.text}>{busy ? "reading…" : "store and read the text"}</button>
          <span className="muted small">or</span>
          <input type="file" accept="image/*,application/pdf,text/plain" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          <button className="primary" onClick={upload} disabled={busy || !form.patient_id || !file}>{busy ? "reading…" : "store and read the photo, scan, or PDF"}</button>
        </div>
        <div className="muted small" style={{ marginTop: 6 }}>A photo or scan is transcribed by the model first, then read like any text. The receipts point into the transcription; the original stays beside it.</div>
        {result && <div style={{ marginTop: 8 }}>{result.error ? <span className="pill red">{result.error}</span> : <span>Stored as <Link to={`/documents/${result.document_id}`}>{result.document_id}</Link> <Status s={result.status} /> {result.kind ? <Kind k={result.kind} /> : null} {result.document_date ? <span className="muted small">dated {fmtDate(result.document_date)}</span> : null} {result.facts?.length ? `· ${result.facts.length} facts` : ""} {result.transcribed ? <span className="muted small">· transcribed from the image</span> : null} {result.note && <span className="muted small">{result.note}</span>}</span>}
          {result.facts?.length > 0 && <table style={{ marginTop: 6 }}><tbody>{result.facts.slice(0, 12).map((f, k) => <tr key={k}><td>{f.display}</td><td><b>{f.value_num ?? f.value_text}</b> {f.unit}{f.attrs?.as_written != null && f.attrs?.unit_as_written && f.attrs.unit_as_written !== f.unit ? <span className="muted small"> (written {f.attrs.as_written} {f.attrs.unit_as_written})</span> : null}</td><td className="muted small">{f.page ? `p.${f.page}` : "not located"}</td><td className="muted small">“{(f.quote || "").replace(/\s+/g, " ").trim()}”</td></tr>)}</tbody></table>}</div>}
      </div>
    </div>
    <div className="card">
      <table><thead><tr><th>Document</th><th>Patient</th><th>From</th><th>Document date</th><th>Received</th><th>Status</th><th>Facts</th><th>Reader</th></tr></thead>
        <tbody>{rows.map((d) => (<tr key={d.id} className="row" onClick={() => nav(`/documents/${d.id}`)}>
          <td><b>{d.id}</b><div className="small"><Kind k={d.kind} /> <span className="muted">· {d.n_pages} page{d.n_pages > 1 ? "s" : ""}</span></div></td><td>{d.patient_id}<div className="muted small">{d.display_name}</div></td><td><Org o={d.source_org} /></td><td>{fmtDate(d.document_date)}</td><td className="muted small">{fmtDT(d.received_at)}</td><td><Status s={d.status} /></td><td>{d.n_facts ?? ""}</td><td className="muted small">{d.reader}</td></tr>))}</tbody></table>
    </div>
  </>);
}
