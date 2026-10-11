import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api.js";
import { Avatar, Empty, Kind, Org, Status, fmtDate } from "../components/ui.jsx";

export default function Patient() {
  const { id } = useParams(); const nav = useNavigate();
  const [p, setP] = useState(null); const [forms, setForms] = useState([]); const [formId, setFormId] = useState("vs_visit"); const [visit, setVisit] = useState(""); const [busy, setBusy] = useState(false); const [err, setErr] = useState(null);
  const [concept, setConcept] = useState(null); const [facts, setFacts] = useState([]);
  const load = () => api.patient(id).then((x) => { setP(x); if (!visit && x.visit_dates.length) setVisit(x.visit_dates[0]); });
  useEffect(() => { load(); api.forms().then(setForms); setConcept(null); }, [id]);
  useEffect(() => { if (concept) api.patientFacts(id, concept).then(setFacts); }, [concept, id]);
  useEffect(() => { if (p?.patient.kind === "child") setFormId("nj_ch14"); }, [p?.patient.kind]);
  if (!p) return <div className="card">Loading…</div>;
  const s = p.patient;
  const run = () => { setBusy(true); setErr(null); api.fill(id, formId, visit || new Date().toISOString().slice(0, 10)).then((i) => nav(`/forms/${i.id}`)).catch((e) => setErr(String(e.message))).finally(() => setBusy(false)); };
  return (<>
    <div className="muted small"><Link to="/patients">Patients</Link> › {s.id}</div>
    <div style={{ display: "flex", alignItems: "baseline", gap: 14, flexWrap: "wrap" }}>
      <Avatar name={s.display_name} id={s.id} /><h2 style={{ margin: "4px 0 8px" }}>{s.display_name} <span className="muted" style={{ fontWeight: 400 }}>{s.id}</span></h2><span className="muted">born {fmtDate(s.birth_date)} · {s.sex} {s.kind === "child" ? "· child" : `· trial ${s.trial_id}, site ${s.site}`}</span>
    </div>
    <div className="card" style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
      <b>Fill a form</b>
      <select value={formId} onChange={(e) => setFormId(e.target.value)}>{forms.map((f) => <option key={f.id} value={f.id}>{f.name} ({f.domain})</option>)}</select>
      <input type="date" value={visit} onChange={(e) => setVisit(e.target.value)} />
      {p.visit_dates.length > 0 && <select value="" onChange={(e) => setVisit(e.target.value)}><option value="">known visit dates…</option>{p.visit_dates.map((d) => <option key={d} value={d}>{d}</option>)}</select>}
      <button className="primary" onClick={run} disabled={busy}>{busy ? "filling…" : "fill and verify"}</button>
      {err && <span className="pill red">{err}</span>}
      <span className="muted small">the filler answers each field from the ledger; the verifier checks every answer against other sources and rules</span>
    </div>
    <div className="grid2">
      <div>
        <div className="card"><h2>Known at</h2>
          {p.identifiers.map((i) => <div key={i.org + i.local_id}><Org o={i.org} /> <span className="muted small">{i.local_id}</span></div>)}
        </div>
        <div className="card"><h2>Documents <span className="muted small">({p.documents.length})</span></h2>
          {p.documents.length ? <table><thead><tr><th>Document</th><th>From</th><th>Date</th><th>Status</th><th>Facts</th></tr></thead>
            <tbody>{p.documents.map((d) => <tr key={d.id} className="row"><td><Link to={`/documents/${d.id}`}><b>{d.id}</b></Link><div className="small"><Kind k={d.kind} /> <span className="muted">· {d.n_pages} page{d.n_pages > 1 ? "s" : ""}</span></div></td><td><Org o={d.source_org} /></td><td>{fmtDate(d.document_date)}</td><td><Status s={d.status} /></td><td>{d.n_facts ?? ""}</td></tr>)}</tbody></table>
            : <Empty>No outside documents yet. Everything known about this patient comes from the hospital record.</Empty>}
        </div>
        <div className="card"><h2>Forms <span className="muted small">({p.forms.length})</span></h2>
          {p.forms.length ? <table><thead><tr><th>Form</th><th>Visit</th><th>Filled</th><th>Flagged</th><th>Status</th><th>Time</th></tr></thead>
            <tbody>{p.forms.map((f) => <tr key={f.id} className="row" onClick={() => nav(`/forms/${f.id}`)}><td><b>{f.name}</b> <span className="muted small">{f.domain}</span></td><td>{fmtDate(f.visit_date)}</td><td>{f.n_filled}/{f.n_fields}</td><td>{f.n_flagged ? <span className="pill red">{f.n_flagged}</span> : <span className="pill green">0</span>}</td><td><Status s={f.status} /></td><td className="muted small">{f.filled_ms} ms</td></tr>)}</tbody></table>
            : <Empty>No forms yet. Pick a form and a visit date above.</Empty>}
        </div>
      </div>
      <div>
        <div className="card"><h2>What the ledger knows</h2>
          <table><thead><tr><th>Concept</th><th>Facts</th><th>Sources</th><th>Latest</th></tr></thead>
            <tbody>{p.concepts.map((c) => <tr key={c.concept} className={`row ${concept === c.concept ? "sel" : ""}`} onClick={() => setConcept(c.concept)}><td>{c.display}</td><td>{c.n}</td><td>{c.sources.map((o) => <Org key={o} o={o} />)}</td><td>{fmtDate(c.latest)}</td></tr>)}</tbody></table>
        </div>
        {concept && <div className="card"><h2>{facts[0]?.display ?? concept} <span className="muted small">newest first</span></h2>
          <table><thead><tr><th>When</th><th>Value</th><th>From</th><th>Receipt</th><th>Conf.</th></tr></thead>
            <tbody>{facts.map((f) => <tr key={f.id}><td>{fmtDate(f.observed_at)}</td><td><b>{f.value_num ?? f.value_text}</b> {f.unit}{f.attrs?.dose ? <span className="muted small"> · {f.attrs.dose}</span> : ""}{f.attrs?.unit_as_written && f.attrs.unit_as_written !== f.unit ? <span className="muted small"> (written {f.attrs.as_written} {f.attrs.unit_as_written})</span> : ""}</td>
              <td><Org o={f.source_org} /></td><td className="small">{f.document_id ? <Link to={`/documents/${f.document_id}#fact-${f.id}`}>{f.document_id} p.{f.page}</Link> : <span className="muted">{f.resource_ref}</span>}{f.quote && <div className="muted">“{f.quote}”</div>}</td><td className="muted small">{Math.round(f.confidence * 100)}%</td></tr>)}</tbody></table>
        </div>}
      </div>
    </div>
  </>);
}
