import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api.js";
import { Status, fmtDate } from "../components/ui.jsx";

export default function Queue() {
  const [rows, setRows] = useState([]); const nav = useNavigate();
  useEffect(() => { api.queue().then(setRows); }, []);
  return (<>
    <h2 style={{ margin: "4px 0 2px" }}>Review queue</h2>
    <div className="muted" style={{ marginBottom: 12 }}>Forms the filler completed. Only flagged fields need a human. Disagreements first.</div>
    <div className="card">
      <table><thead><tr><th>Form</th><th>Patient</th><th>Visit</th><th>Filled</th><th>Flagged</th><th>To resolve</th><th>Status</th><th>Fill time</th></tr></thead>
        <tbody>{rows.map((r) => (<tr key={r.id} className="row" onClick={() => nav(`/forms/${r.id}`)}>
          <td><b>{r.name}</b> <span className="muted small">{r.domain} · #{r.id}</span></td><td><Link to={`/patients/${r.patient_id}`} onClick={(e) => e.stopPropagation()}>{r.patient_id}</Link><div className="muted small">{r.display_name}{r.kind === "child" ? " · child" : ""}</div></td>
          <td>{fmtDate(r.visit_date)}</td><td>{r.n_filled}/{r.n_fields}</td><td>{r.n_flagged ? <span className="pill red">{r.n_flagged}</span> : <span className="pill green">0</span>}</td>
          <td>{r.unresolved > 0 ? <span className="pill amber">{r.unresolved}</span> : <span className="muted">–</span>}</td><td><Status s={r.status} /></td><td className="muted small">{r.filled_ms} ms</td></tr>))}</tbody></table>
      {rows.length === 0 && <div className="muted">Nothing to review. Fill a form from a patient page.</div>}
    </div>
  </>);
}
