import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { Clock, Status, fmtDate } from "../components/ui.jsx";

export default function FdaQueue() {
  const [rows, setRows] = useState([]);
  useEffect(() => { api.fda().then(setRows); }, []);
  return (<>
    <h2 style={{ margin: "4px 0 2px" }}>Expedited reports</h2>
    <div className="muted" style={{ marginBottom: 12 }}>Pre-filled from the case or the patient profile. A provider verifies every field and signs before anything is submitted. Submission is mocked.</div>
    <div className="card">
      <table><thead><tr><th>Form</th><th>Source</th><th>Event</th><th>Clock</th><th>Due</th><th>Status</th><th>Verified by</th></tr></thead>
        <tbody>{rows.map((f) => (
          <tr key={f.id} className="row"><td><Link to={`/fda/${f.id}`}><b>#{f.id}</b></Link></td>
            <td>{f.source_type === "intake_case" ? <Link to={`/intake/${f.source_id}`}>{f.source_id}</Link> : <Link to={`/patients/${f.source_id}`}>{f.source_id}</Link>}<div className="muted small">{f.source_type.replace("_", " ")}</div></td>
            <td>{f.reactions}</td><td><Clock expedited={!!f.clock_days} daysLeft={f.days_left} clock={f.clock_days} /></td><td>{fmtDate(f.due_date)}</td><td><Status s={f.status} /></td><td>{f.verified_by ?? ""}</td></tr>))}</tbody></table>
      {rows.length === 0 && <div className="muted">Nothing queued.</div>}
    </div>
  </>);
}
