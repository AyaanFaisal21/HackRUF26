import React, { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api.js";
import { LogicChain, Status, fmtDate, fmtDT } from "../components/ui.jsx";
import { SymptomChart, LabChart } from "../components/charts.jsx";

const ITEMS = ["nausea", "fatigue", "headache", "rash", "diarrhea", "dizziness", "appetite loss", "sleep problems"];

function Brief({ b, subjectId, onSigned }) {
  const body = b.body; const [a, setA] = useState({ physician: "", relatedness: "possible", serious: false, fatal: false, life_threatening: false, hospitalization: false, disability: false, other_medically_important: false, expected: false, dechallenge: "unknown", event: body.flags[0]?.title ?? "", comment: "" });
  const [result, setResult] = useState(null);
  const set = (k, v) => setA({ ...a, [k]: v });
  const sign = () => api.sign(b.id, a).then((r) => { setResult(r); onSigned(); });
  const List = ({ title, items }) => items?.length ? (<><h3>{title}</h3><ul style={{ margin: "4px 0 0 18px" }}>{items.map((x, i) => <li key={i}>{x}</li>)}</ul></>) : null;
  return (
    <div className="card" style={{ borderColor: "#c7d2fe" }}>
      <div style={{ display: "flex", gap: 8, alignItems: "baseline" }}><h2 style={{ margin: 0 }}>Physician brief</h2><span className="muted small">generated {fmtDT(b.generated_at)} · brief #{b.id}</span>{b.signed_by && <span className="pill green" style={{ marginLeft: "auto" }}>signed by {b.signed_by}</span>}</div>
      {body.narrative && <p style={{ whiteSpace: "pre-wrap" }}>{body.narrative}</p>}
      {!body.narrative && <div className="muted small">No model key configured: deterministic brief only, no narrative paragraph.</div>}
      <h3>Flags considered</h3>{body.flags.map((f) => <div key={f.id} className="small">• {f.title} <span className="muted">({f.rule}, {f.fired_on})</span></div>)}
      <div className="grid2">
        <div><h3>Laboratory peaks</h3><table><tbody>{body.labs.map((l) => <tr key={l.test}><td>{l.test}</td><td>{l.peak_x_uln}x ULN on {fmtDate(l.peak_date)}</td><td>grade {l.grade}</td><td className="muted small">baseline {l.baseline_x_uln ?? "–"}x</td></tr>)}</tbody></table></div>
        <div><h3>Patient-reported symptoms, severe days</h3><table><tbody>{body.symptoms.length ? body.symptoms.map((s) => <tr key={s.item}><td>{s.item}</td><td>{s.days_severe} days ≥3</td><td className="muted small">{fmtDate(s.first_severe)} to {fmtDate(s.last_severe)}</td></tr>) : <tr><td className="muted">none at grade 3 or above</td></tr>}</tbody></table></div>
      </div>
      <div className="grid2"><List title="Arguments for drug relatedness" items={body.arguments_for_relatedness} /><List title="Arguments against" items={body.arguments_against} /></div>
      <h3>Cohort context</h3><div className="small">Same pattern in other subjects: {Object.keys(body.cohort.subjects_with_same_pattern).length ? Object.entries(body.cohort.subjects_with_same_pattern).map(([k, v]) => `${k} ×${v}`).join(", ") : "none"} {body.cohort.similar_subjects.length > 0 && <span className="muted">({body.cohort.similar_subjects.map((s) => <Link key={s} to={`/patients/${s}`}>{s} </Link>)})</span>}</div>
      <h3>Regulatory</h3><div className="small">{body.regulatory.note}<div className="muted">§ {body.regulatory.citation}</div></div>
      {b.assessment ? (<><h3>Assessment</h3><div className="small">{b.assessment.relatedness} · {b.assessment.serious ? "serious" : "not serious"} · {b.assessment.expected ? "expected" : "unexpected"} · {b.assessment.comment}</div></>) : (<>
        <h3>Investigator assessment</h3>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
          <input placeholder="physician name" value={a.physician} onChange={(e) => set("physician", e.target.value)} />
          <select value={a.relatedness} onChange={(e) => set("relatedness", e.target.value)}>{["not_related", "unlikely", "possible", "probable", "definite"].map((r) => <option key={r}>{r}</option>)}</select>
          <select value={a.dechallenge} onChange={(e) => set("dechallenge", e.target.value)}><option value="unknown">dechallenge unknown</option><option value="yes">abated after stop</option><option value="no">did not abate</option></select>
        </div>
        <div style={{ marginTop: 8 }}>{["serious", "fatal", "life_threatening", "hospitalization", "disability", "other_medically_important", "expected"].map((k) => <label key={k} className="inl"><input type="checkbox" checked={a[k]} onChange={(e) => set(k, e.target.checked)} />{k.replace(/_/g, " ")}</label>)}</div>
        <textarea placeholder="comment" value={a.comment} onChange={(e) => set("comment", e.target.value)} style={{ width: "100%", minHeight: 50, marginTop: 6 }} />
        <div style={{ marginTop: 8 }}><button className="primary" disabled={!a.physician} onClick={sign}>sign assessment</button> <span className="muted small">serious + unexpected + possibly related creates a pre-filled expedited report in the FDA queue</span></div>
      </>)}
      {result && <div style={{ marginTop: 8 }}>{result.form_id ? <span>Expedited report drafted: <Link to={`/fda/${result.form_id}`}>form #{result.form_id}</Link></span> : <span className="muted">Signed. No expedited report required on this assessment.</span>}</div>}
    </div>);
}

export default function Patient() {
  const { id } = useParams();
  const [p, setP] = useState(null); const [items, setItems] = useState(null); const [busy, setBusy] = useState(false);
  const load = () => api.subject(id).then(setP);
  useEffect(() => { load(); setItems(null); }, [id]);
  if (!p) return <div className="card">Loading…</div>;
  const s = p.subject;
  const maxByItem = Object.fromEntries(ITEMS.map((it) => [it, Math.max(0, ...p.diaries.filter((d) => d.item === it).map((d) => d.grade))]));
  const shown = items ?? ITEMS.filter((it) => maxByItem[it] >= 2);
  const decide = (fid, status) => api.decideFlag(fid, status, "physician").then(load);
  const gen = () => { setBusy(true); api.brief(id, true).then(load).finally(() => setBusy(false)); };
  const dayDate = (d) => (d == null ? "" : fmtDate(new Date(new Date(s.ref_date).getTime() + (d - 1) * 86400000)));
  return (<>
    <div className="muted small"><Link to="/trials">Studies</Link> › <Link to={`/trials/${s.trial_id}`}>{s.trial_id}</Link> › {s.id}</div>
    <div style={{ display: "flex", alignItems: "baseline", gap: 14, flexWrap: "wrap" }}>
      <h2 style={{ margin: "4px 0 8px" }}>{s.id}</h2><span className="muted">site {s.site} · {s.age} {s.sex} · day {s.last_day} on study · day 1 = {fmtDate(s.ref_date)} · {p.trial.product}</span>
      <span style={{ marginLeft: "auto" }}><button className="primary" onClick={gen} disabled={busy}>{busy ? "generating…" : "generate physician report"}</button></span>
    </div>
    <div className="grid2">
      <div>
        <div className="card"><h2>Flags <span className="muted small">({p.flags.filter((f) => f.status === "open").length} open)</span></h2>
          {p.flags.length ? p.flags.map((f) => <LogicChain key={f.id} flag={f} onDecide={decide} />) : <div className="muted">No flags. Nothing has crossed a threshold for this subject.</div>}
        </div>
        <div className="card"><h2>Self-reported symptoms <span className="muted small">(daily, 0 none to 4 very severe)</span></h2>
          <div className="chips">{ITEMS.map((it) => <span key={it} className={`chip ${shown.includes(it) ? "on" : ""}`} onClick={() => setItems(shown.includes(it) ? shown.filter((x) => x !== it) : [...shown, it])}>{it} <span className="muted">max {maxByItem[it]}</span></span>)}</div>
          <SymptomChart diaries={p.diaries} items={shown} />
        </div>
        <div className="card"><h2>Liver panel <span className="muted small">(multiples of the upper limit of normal)</span></h2><LabChart labs={p.labs} /></div>
        <div className="card"><h2>Recorded adverse events <span className="muted small">({p.events.length})</span></h2>
          <table><thead><tr><th>Event</th><th>Start</th><th>End</th><th>Severity</th><th>Serious</th></tr></thead>
            <tbody>{p.events.map((e, i) => <tr key={i}><td>{e.pt ?? e.term}</td><td>{dayDate(e.start_day)}</td><td>{dayDate(e.end_day) || <span className="muted">ongoing</span>}</td><td>{e.severity}</td><td>{e.serious ? <span className="pill red">yes</span> : ""}</td></tr>)}</tbody></table>
        </div>
      </div>
      <div>
        {p.briefs.length ? p.briefs.map((b) => <Brief key={b.id} b={b} subjectId={id} onSigned={load} />) : <div className="card muted">No physician report yet. Generate one when a flag needs a decision: it assembles the timeline, the arguments for and against drug relatedness, and the cohort context, and never states a conclusion on its own.</div>}
        {p.forms.length > 0 && <div className="card"><h3>Expedited reports</h3>{p.forms.map((f) => <div key={f.id}><Link to={`/fda/${f.id}`}>form #{f.id}</Link> <Status s={f.status} /> {f.due_date && <span className="muted small">due {fmtDate(f.due_date)} ({f.clock_days}-day clock)</span>}</div>)}</div>}
      </div>
    </div>
  </>);
}
