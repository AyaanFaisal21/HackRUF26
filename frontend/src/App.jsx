import React, { useEffect, useState } from "react";
import { getQueue, getStats, getCase, getHistory, decideDuplicate } from "./api.js";

const clockPill = (c) => {
  if (!c.expedited) return <span className="pill muted">no clock</span>;
  if (c.days_left < 0) return <span className="pill red">overdue {-c.days_left}d</span>;
  if (c.days_left <= 2) return <span className="pill red">{c.days_left}d left</span>;
  if (c.days_left <= 5) return <span className="pill amber">{c.days_left}d left</span>;
  return <span className="pill green">{c.days_left}d left</span>;
};

function Highlighted({ body, spans }) {
  const ss = spans.filter((s) => s.start != null).sort((a, b) => a.start - b.start);
  const out = []; let i = 0;
  ss.forEach((s, k) => { if (s.start < i) return; out.push(body.slice(i, s.start)); out.push(<mark key={k} title={s.label}>{body.slice(s.start, s.end)}</mark>); i = s.end; });
  out.push(body.slice(i));
  return <pre className="body">{out}</pre>;
}

function CaseDetail({ id, onChange }) {
  const [d, setD] = useState(null); const [hist, setHist] = useState([]);
  const load = () => { getCase(id).then(setD); getHistory(id).then(setHist); };
  useEffect(load, [id]);
  if (!d) return <div className="card">Loading…</div>;
  const { state, assessment } = d.case;
  const spansFor = (ext) => [
    ...ext.patient.evidence.map((e) => ({ ...e, label: "patient" })), ...ext.reporter.evidence.map((e) => ({ ...e, label: "reporter" })),
    ...ext.drugs.flatMap((x) => x.evidence.map((e) => ({ ...e, label: "drug" }))), ...ext.reactions.flatMap((x) => x.evidence.map((e) => ({ ...e, label: "reaction" }))),
    ...ext.seriousness.evidence.map((e) => ({ ...e, label: "seriousness" })),
  ];
  return (
    <div className="card">
      <h2 style={{ margin: 0 }}>{id} <span className="pill">{d.status}</span></h2>
      <div className="muted">{state.snapshots[0].extraction.summary}</div>
      <h3>Assessment</h3>
      <div>
        {assessment.valid ? <span className="pill green">valid</span> : <span className="pill red">not valid: {assessment.missing.join(", ")}</span>}
        {assessment.criteria.map((c) => <span key={c} className="pill red">{c.replace(/_/g, " ")}</span>)}
        <span className="pill">{assessment.expectedness}</span>
        {assessment.day_zero && <span className="pill">day zero {assessment.day_zero}</span>}
        {assessment.due_date && <span className="pill">due {assessment.due_date} ({assessment.clock_days}-day clock)</span>}
      </div>
      <div className="muted" style={{ marginTop: 6 }}>{assessment.citations.map((c) => <div key={c}>§ {c}</div>)}</div>
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
          <div key={other} style={{ marginBottom: 6 }}>
            <b>{other}</b> <span className={`pill ${x.verdict === "likely" ? "red" : "amber"}`}>{x.verdict} {Math.round(x.score * 100)}%</span>
            <span className="muted"> structured {Math.round(x.structured * 100)}% · semantic {Math.round(x.semantic * 100)}% · {Object.entries(x.evidence).map(([k, v]) => `${k} ${Math.round(v * 100)}%`).join(", ")}</span>
            {!x.decided && <> <button onClick={() => decideDuplicate(id, other, true).then(() => { load(); onChange(); })}>merge</button> <button onClick={() => decideDuplicate(id, other, false).then(load)}>not a duplicate</button></>}
            {x.decided && <span className="pill">{x.decided}</span>}
          </div>); })}</>)}
      <h3>Source messages ({d.messages.length})</h3>
      {d.messages.map((m) => (<div key={m.id}><div className="muted">{m.id} · {m.channel} · {new Date(m.received_at).toLocaleString()} {m.subject ? `· ${m.subject}` : ""}</div><Highlighted body={m.body} spans={spansFor(m.extraction)} /></div>))}
      <h3>History</h3>
      <table><tbody>{hist.map((h, i) => <tr key={i}><td className="muted">{new Date(h.at).toLocaleString()}</td><td>{h.actor}</td><td>{h.action}{h.field ? ` · ${h.field}` : ""}{h.reason ? ` · ${h.reason}` : ""}</td></tr>)}</tbody></table>
    </div>
  );
}

export default function App() {
  const [queue, setQueue] = useState([]); const [stats, setStats] = useState(null); const [sel, setSel] = useState(null);
  const refresh = () => { getQueue().then(setQueue); getStats().then(setStats); };
  useEffect(refresh, []);
  return (<>
    <header><h1>Day Zero</h1><small>safety intake queue · the model extracts, the rules decide, you confirm</small>
      {stats && <div className="stats"><span><b>{stats.messages}</b> messages</span><span><b>{stats.cases}</b> cases</span><span style={{ color: stats.overdue ? "var(--red)" : undefined }}><b>{stats.overdue}</b> overdue</span><span><b>{stats.open_duplicates}</b> open duplicates</span></div>}
    </header>
    <main>
      <div className="card">
        <table><thead><tr><th>Case</th><th>Validity</th><th>Seriousness</th><th>Day zero</th><th>Clock</th><th>Dups</th></tr></thead>
          <tbody>{queue.map((c) => (
            <tr key={c.id} className={`row ${sel === c.id ? "sel" : ""}`} onClick={() => setSel(c.id)}>
              <td><b>{c.id}</b><div className="muted">{c.patient_initials ?? ""} {c.patient_age ?? ""} {c.patient_sex ?? ""} · {c.reporter_qualification ?? "unknown reporter"} · {c.n_messages} msg</div></td>
              <td>{c.valid ? <span className="pill green">valid</span> : <span className="pill amber">missing {c.missing.map((m) => m.replace("identifiable_", "")).join(", ")}</span>}</td>
              <td>{c.criteria.map((x) => <span key={x} className="pill red">{x.replace(/_/g, " ")}</span>)}{!c.serious && <span className="pill muted">non-serious</span>}</td>
              <td>{c.day_zero ?? <span className="muted">—</span>}</td>
              <td>{clockPill(c)}</td>
              <td>{c.open_duplicates > 0 ? <span className="pill amber">{c.open_duplicates}</span> : ""}</td>
            </tr>))}</tbody></table>
      </div>
      {sel ? <CaseDetail id={sel} onChange={refresh} /> : <div className="card muted">Select a case. Every field links back to the text it came from.</div>}
    </main>
  </>);
}
