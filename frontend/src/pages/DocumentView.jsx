import React, { useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { api } from "../api.js";
import { Highlight, Kind, Org, Status, fmtDate } from "../components/ui.jsx";

export default function DocumentView() {
  const { id } = useParams(); const loc = useLocation();
  const [d, setD] = useState(null); const [active, setActive] = useState(null);
  useEffect(() => { api.document(id).then((x) => { setD(x); const m = loc.hash.match(/fact-(\d+)/); if (m) { setActive(Number(m[1])); setTimeout(() => document.getElementById(`fact-${m[1]}`)?.scrollIntoView({ block: "center" }), 50); } }); }, [id]);
  if (!d) return <div className="card">Loading…</div>;
  return (<>
    <div className="muted small"><Link to="/documents">Documents</Link> › <Link to={`/patients/${d.patient_id}`}>{d.patient_id}</Link> › {d.id}</div>
    <div style={{ display: "flex", alignItems: "baseline", gap: 12, flexWrap: "wrap" }}>
      <h2 style={{ margin: "4px 0 8px" }}>{d.id}</h2><Kind k={d.kind} /><Org o={d.source_org} /><Status s={d.status} />
      <span className="muted small">dated {fmtDate(d.document_date)} · {d.n_pages} page{d.n_pages > 1 ? "s" : ""} · sha256 {d.sha256.slice(0, 12)}… · read by {d.reader}</span>
    </div>
    <div className="grid2">
      <div className="card"><h2>Text as received <span className="muted small">(highlights are the receipts)</span></h2><Highlight text={d.text} spans={d.facts} active={active} /></div>
      <div className="card sticky"><h2>Facts read from this document <span className="muted small">({d.facts.length})</span></h2>
        <table><thead><tr><th>Fact</th><th>Value</th><th>When</th><th>Page</th><th>Conf.</th></tr></thead>
          <tbody>{d.facts.map((f) => <tr key={f.id} className={`row ${active === f.id ? "sel" : ""}`} onClick={() => { setActive(f.id); document.getElementById(`fact-${f.id}`)?.scrollIntoView({ block: "center" }); }}>
            <td>{f.display}{f.attrs?.dose ? <div className="muted small">{f.attrs.dose} {f.attrs.frequency ?? ""}</div> : ""}</td><td><b>{f.value_num ?? f.value_text}</b> {f.unit}{f.attrs?.unit_as_written && f.attrs.unit_as_written !== f.unit ? <div className="muted small">written {f.attrs.as_written} {f.attrs.unit_as_written}</div> : ""}</td>
            <td>{fmtDate(f.observed_at)}</td><td>{f.page ?? <span className="pill amber">not located</span>}</td><td className="muted small">{Math.round(f.confidence * 100)}%</td></tr>)}</tbody></table>
      </div>
    </div>
  </>);
}
