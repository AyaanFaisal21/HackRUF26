import React, { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api.js";
import { Clock, Stat, fmtDT } from "../components/ui.jsx";

function Highlighted({ body, spans }) {
  const ss = spans.filter((s) => s.start != null).sort((a, b) => a.start - b.start);
  const out = []; let i = 0;
  ss.forEach((s, k) => { if (s.start < i) return; out.push(body.slice(i, s.start)); out.push(<mark key={k} title={s.label}>{body.slice(s.start, s.end)}</mark>); i = s.end; });
  out.push(body.slice(i));
  return <pre className="body">{out}</pre>;
}

function CaseDetail({ id, onChange }) {
  const [d, setD] = useState(null); const [hist, setHist] = useState([]); const [formId, setFormId] = useState(null);
  const load = () => { api.case(id).then(setD); api.history(id).then(setHist); };
  useEffect(() => { load(); setFormId(null); }, [id]);
  if (!d) return <div className="card">Loading…</div>;
  const { state, assessment } = d.case;
  const spansFor = (ext) => [...ext.patient.evidence.map((e) => ({ ...e, label: "patient" })), ...ext.reporter.evidence.map((e) => ({ ...e, label: "reporter" })),
    ...ext.drugs.flatMap((x) => x.evidence.map((e) => ({ ...e, label: "drug" }))), ...ext.reactions.flatMap((x) => x.evidence.map((e) => ({ ...e, label: "reaction" }))), ...ext.seriousness.evidence.map((e) => ({ ...e, label: "seriousness" }))];
  return (
    <div className="card">
      <div style={{ display: "flex", gap: 8, alignItems: "baseline" }}><h2 style={{ margin: 0 }}>{id}</h2><span className="pill">{d.status}</span>
        {assessment.expedited && <span style={{ marginLeft: "auto" }}><button className="primary" onClick={() => api.caseForm(id).then((r) => setFormId(r.form_id))}>draft expedited report</button></span>}</div>
      {formId && <div className="small">Pre-filled report queued: <Link to={`/fda/${formId}`}>form #{formId}</Link></div>}
      <div className="muted">{state.snapshots[0].extraction.summary}</div>
      <h3>Assessment</h3>
      <div>{assessment.valid ? <span className="pill green">valid</span> : <span className="pill red">not valid: {assessment.missing.join(", ")}</span>}
        {assessment.criteria.map((c) => <span key={c} className="pill red">{c.replace(/_/g, " ")}</span>)}<span className="pill">{assessment.expectedness}</span>
        {assessment.day_zero && <span className="pill">day zero {assessment.day_zero}</span>}{assessment.due_date && <span className="pill">due {assessment.due_date} ({assessment.clock_days}-day clock)</span>}</div>
      <div className="muted small" style={{ marginTop: 6 }}>{assessment.citations.map((c) => <div key={c}>§ {c}</div>)}</div>
      {assessment.followup_questions.length > 0 && (<><h3>Drafted follow-up questions</h3><ul>{assessment.followup_questions.map((q) => <li key={q}>{q}</li>)}</ul></>)}
      <h3>Extracted</h3>
      <table><tbody>
        <tr><td>Patient</td><td>{state.patient.identifiable ? `${state.patient.initials ?? ""} ${state.patient.age ?? "?"}y ${state.patient.sex}` : <i className="muted">not identifiable</i>}</td></tr>
        <tr><td>Reporter</td><td>{state.reporter.identifiable ? `${state.reporter.name} (${state.reporter.qualification})` : <i className="muted">not identifiable</i>}</td></tr>
        <tr><td>Suspect product</td><td>{state.drugs.filter((x) => x.role === "suspect").map((x) => x.name).join(", ") || <i className="muted">none</i>}</td></tr>
        <tr><td>Reactions</td><td>{state.reactions.map((r) => <div key={r.term}>{r.term} → <b>{r.pt ?? "uncoded"}</b> <span className="muted">({r.outcome})</span></div>)}</td></tr>
      </tbody></table>
      {d.duplicates.length > 0 && (<><h3>Possible duplicates</h3>
        {d.duplicates.map((x) => { const other = x.case_id === id ? x.other_case_id : x.case_id; return (
          <div key={other} style={{ marginBottom: 6 }}><b>{other}</b> <span className={`pill ${x.verdict === "likely" ? "red" : "amber"}`}>{x.verdict} {Math.round(x.score * 100)}%</span>
            <span className="muted small"> structured {Math.round(x.structured * 100)}% · semantic {Math.round(x.semantic * 100)}% · {Object.entries(x.evidence).map(([k, v]) => `${k} ${Math.round(v * 100)}%`).join(", ")}</span>
            {!x.decided && <> <button onClick={() => api.decideDuplicate(id, other, true).then(() => { load(); onChange(); })}>merge</button> <button onClick={() => api.decideDuplicate(id, other, false).then(load)}>not a duplicate</button></>}
            {x.decided && <span className="pill">{x.decided}</span>}</div>); })}</>)}
      <h3>Source messages ({d.messages.length})</h3>
      {d.messages.map((m) => (<div key={m.id}><div className="muted small">{m.id} · {m.channel} · {fmtDT(m.received_at)} {m.subject ? `· ${m.subject}` : ""}</div><Highlighted body={m.body} spans={spansFor(m.extraction)} /></div>))}
      <h3>History</h3>
      <table><tbody>{hist.map((h, i) => <tr key={i}><td className="muted small">{fmtDT(h.at)}</td><td>{h.actor}</td><td>{h.action}{h.field ? ` · ${h.field}` : ""}{h.reason ? ` · ${h.reason}` : ""}</td></tr>)}</tbody></table>
    </div>);
}

export default function Intake() {
  const { id } = useParams(); const nav = useNavigate();
  const [queue, setQueue] = useState([]); const [stats, setStats] = useState(null);
  const refresh = () => { api.queue().then(setQueue); api.stats().then(setStats); };
  useEffect(refresh, []);
  return (<>
    <div style={{ display: "flex", alignItems: "baseline", gap: 16, marginBottom: 10 }}><h2 style={{ margin: 0 }}>Intake queue</h2><span className="muted">the model extracts, the rules decide, you confirm</span>
      {stats && <div className="stats" style={{ marginLeft: "auto" }}><Stat n={stats.messages} label="messages" /><Stat n={stats.cases} label="cases" /><Stat n={stats.overdue} label="overdue" warn={stats.overdue > 0} /><Stat n={stats.open_duplicates} label="open duplicates" /></div>}</div>
    <div className="grid2">
      <div className="card">
        <table><thead><tr><th>Case</th><th>Validity</th><th>Seriousness</th><th>Day zero</th><th>Clock</th><th>Dups</th></tr></thead>
          <tbody>{queue.map((c) => (
            <tr key={c.id} className={`row ${id === c.id ? "sel" : ""}`} onClick={() => nav(`/intake/${c.id}`)}>
              <td><b>{c.id}</b><div className="muted small">{c.patient_initials ?? ""} {c.patient_age ?? ""} {c.patient_sex ?? ""} · {c.reporter_qualification ?? "unknown reporter"} · {c.n_messages} msg</div></td>
              <td>{c.valid ? <span className="pill green">valid</span> : <span className="pill amber">missing {c.missing.map((m) => m.replace("identifiable_", "")).join(", ")}</span>}</td>
              <td>{c.criteria.map((x) => <span key={x} className="pill red">{x.replace(/_/g, " ")}</span>)}{!c.serious && <span className="pill muted">non-serious</span>}</td>
              <td>{c.day_zero ?? <span className="muted">—</span>}</td><td><Clock expedited={c.expedited} daysLeft={c.days_left} clock={c.clock_days} /></td>
              <td>{c.open_duplicates > 0 ? <span className="pill amber">{c.open_duplicates}</span> : ""}</td></tr>))}</tbody></table>
      </div>
      {id ? <CaseDetail id={id} onChange={refresh} /> : <div className="card muted">Select a case. Every field links back to the text it came from.</div>}
    </div>
  </>);
}
