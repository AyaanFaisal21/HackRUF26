import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { Stat, fmtDate } from "../components/ui.jsx";

export default function Patients() {
  const [rows, setRows] = useState([]); const [q, setQ] = useState(""); const [kind, setKind] = useState(""); const [stats, setStats] = useState(null);
  useEffect(() => { api.patients(q, kind).then(setRows); }, [q, kind]);
  useEffect(() => { api.stats().then(setStats); }, []);
  return (<>
    <div style={{ display: "flex", alignItems: "baseline", gap: 16, marginBottom: 10 }}>
      <h2 style={{ margin: 0 }}>Patients</h2><span className="muted">one ledger per patient, every fact with its origin</span>
      {stats && <div className="stats" style={{ marginLeft: "auto" }}><Stat n={stats.patients} label="patients" /><Stat n={stats.facts?.toLocaleString()} label="facts" /><Stat n={stats.sources} label="sources" /><Stat n={stats.documents} label="documents" /><Stat n={stats.forms} label="forms" /></div>}
    </div>
    <div className="card">
      <div className="chips">
        {[["", "all"], ["adult", "trial subjects"], ["child", "children"]].map(([k, l]) => <span key={k} className={`chip ${kind === k ? "on" : ""}`} onClick={() => setKind(k)}>{l}</span>)}
        <input placeholder="search id or name" value={q} onChange={(e) => setQ(e.target.value)} style={{ marginLeft: "auto", width: 240 }} />
      </div>
      <table><thead><tr><th>Patient</th><th>Born</th><th>Sex</th><th>Clinics</th><th>Documents</th><th>Facts</th><th>Open forms</th><th>Flagged fields</th></tr></thead>
        <tbody>{rows.map((p) => (<tr key={p.id} className="row">
          <td><Link to={`/patients/${p.id}`}><b>{p.id}</b></Link><div className="muted small">{p.display_name} {p.kind === "child" ? "· child" : p.site ? `· site ${p.site}` : ""}</div></td>
          <td>{fmtDate(p.birth_date)}</td><td>{p.sex}</td><td>{p.n_orgs}</td><td>{p.n_documents || <span className="muted">–</span>}</td><td>{p.n_facts}</td>
          <td>{p.forms_open || ""}</td><td>{p.flagged > 0 ? <span className="pill red">{p.flagged}</span> : ""}</td></tr>))}</tbody></table>
      <div className="muted small" style={{ marginTop: 6 }}>{rows.length} shown. Patients with documents sort first.</div>
    </div>
  </>);
}
