import React, { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api.js";
import { Sev, LogicChain, fmtDate } from "../components/ui.jsx";

const sevName = { 3: "urgent", 2: "review", 1: "watch" };
export default function Trial() {
  const { id } = useParams();
  const [d, setD] = useState(null); const [filter, setFilter] = useState("flagged"); const [q, setQ] = useState("");
  useEffect(() => { api.trial(id).then(setD); }, [id]);
  if (!d) return <div className="card">Loading…</div>;
  const subs = d.subjects.filter((s) => (filter === "all" || (filter === "flagged" && s.open_flags > 0) || (filter === "urgent" && s.top_severity === 3)) && (!q || s.id.includes(q) || s.site.includes(q)));
  return (<>
    <div className="muted small"><Link to="/trials">Studies</Link> › {d.trial.id}</div>
    <h2 style={{ margin: "4px 0 2px" }}>{d.trial.name}</h2>
    <div className="muted" style={{ marginBottom: 12 }}>{d.trial.product} · {d.trial.sites.length} sites · {d.subjects.length} subjects · arm hidden from this view</div>
    {d.site_flags.length > 0 && <div className="card"><h3>Trial-level flags</h3>{d.site_flags.map((f) => <LogicChain key={f.id} flag={f} />)}</div>}
    <div className="card">
      <div className="chips">
        {["flagged", "urgent", "all"].map((f) => <span key={f} className={`chip ${filter === f ? "on" : ""}`} onClick={() => setFilter(f)}>{f}</span>)}
        <input placeholder="subject or site" value={q} onChange={(e) => setQ(e.target.value)} style={{ marginLeft: "auto" }} />
      </div>
      <table>
        <thead><tr><th>Subject</th><th>Site</th><th>Age / sex</th><th>Day on study</th><th>Last diary</th><th>Symptom burden (7d)</th><th>Latest ALT</th><th>Flags</th></tr></thead>
        <tbody>{subs.map((s) => (
          <tr key={s.id} className="row"><td><Link to={`/patients/${s.id}`}><b>{s.id}</b></Link></td><td>{s.site}</td><td>{s.age} {s.sex}</td><td>{s.last_day}</td><td>{fmtDate(s.last_diary)}</td>
            <td>{s.symptom_burden_7d ?? "–"}</td><td>{s.latest_alt_x_uln != null ? <span className={s.latest_alt_x_uln >= 3 ? "pill red" : s.latest_alt_x_uln > 1 ? "pill amber" : ""}>{s.latest_alt_x_uln}x ULN</span> : "–"}</td>
            <td>{s.open_flags > 0 ? <><Sev s={sevName[s.top_severity]} /> {s.open_flags}</> : <span className="muted">–</span>}</td></tr>))}</tbody>
      </table>
      <div className="muted small" style={{ marginTop: 6 }}>{subs.length} shown</div>
    </div>
  </>);
}
