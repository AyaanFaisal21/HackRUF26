import React, { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api.js";
import { Status, fmtDate } from "../components/ui.jsx";

const show = (v) => (v === null || v === undefined || v === "" ? <i className="muted">not available</i> : Array.isArray(v) ? (v.length ? v.join(", ") : <i className="muted">none</i>) : typeof v === "boolean" ? (v ? "yes" : "no") : String(v));

export default function FdaForm() {
  const { id } = useParams();
  const [f, setF] = useState(null); const [checked, setChecked] = useState({}); const [actor, setActor] = useState("");
  const load = () => api.form(id).then((x) => { setF(x); setChecked({}); });
  useEffect(() => { load(); }, [id]);
  if (!f) return <div className="card">Loading…</div>;
  const body = f.body; const keys = Object.entries(body.sections).flatMap(([sec, fields]) => fields.map((fl) => `${sec}|${fl.label}`));
  const verified = new Set(body.verified_fields || []); const pending = keys.filter((k) => !verified.has(k));
  const selected = Object.keys(checked).filter((k) => checked[k]);
  const pct = Math.round((verified.size / keys.length) * 100);
  return (<>
    <div className="muted small"><Link to="/fda">Expedited reports</Link> › form #{f.id}</div>
    <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}><h2 style={{ margin: "4px 0 8px" }}>Expedited report #{f.id}</h2><Status s={f.status} />
      <span className="muted">source {f.source_type === "intake_case" ? <Link to={`/intake/${f.source_id}`}>{f.source_id}</Link> : <Link to={`/patients/${f.source_id}`}>{f.source_id}</Link>} · {f.clock_days ? `${f.clock_days}-day clock, due ${fmtDate(f.due_date)}` : "no clock"}</span></div>
    <div className="card">
      <div style={{ display: "flex", gap: 12, alignItems: "center" }}><div className="progress" style={{ flex: 1 }}><i style={{ width: `${pct}%` }} /></div><span className="small">{verified.size}/{keys.length} fields verified</span></div>
      <div className="muted small" style={{ marginTop: 4 }}>Modelled on the sections of FDA Form 3500A. Each value shows where it came from. Tick what you have checked against the source, then sign.</div>
    </div>
    {Object.entries(body.sections).map(([sec, fields]) => (
      <div key={sec} className="card"><h2>{sec}</h2>
        {fields.map((fl) => { const k = `${sec}|${fl.label}`; const done = verified.has(k); return (
          <div key={k} className="form-field"><div className="muted">{fl.label}</div><div>{show(fl.value)}</div><div className="src">from: {fl.source}</div>
            <div>{done ? <span className="pill green">✓</span> : <input type="checkbox" checked={!!checked[k]} onChange={(e) => setChecked({ ...checked, [k]: e.target.checked })} />}</div></div>); })}
      </div>))}
    <div className="card" style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
      <input placeholder="your name" value={actor} onChange={(e) => setActor(e.target.value)} />
      <button onClick={() => setChecked(Object.fromEntries(pending.map((k) => [k, true])))} disabled={!pending.length}>select all remaining</button>
      <button className="primary" disabled={!actor || !selected.length} onClick={() => api.verify(f.id, selected, actor).then(load)}>verify {selected.length} field{selected.length === 1 ? "" : "s"} and sign</button>
      <button className="primary" disabled={f.status !== "verified"} onClick={() => api.submit(f.id).then(load)}>submit (mock gateway)</button>
      {f.signed_by || body.signed_by ? <span className="muted small">signed by {f.verified_by ?? body.signed_by}{f.submitted_at ? ` · submitted ${fmtDate(f.submitted_at)}` : ""}</span> : null}
    </div>
  </>);
}
