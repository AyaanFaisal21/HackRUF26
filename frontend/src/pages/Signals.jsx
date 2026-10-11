import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { WeeklyBars } from "../components/charts.jsx";
import { Sev } from "../components/ui.jsx";

const ITEMS = ["nausea", "fatigue", "headache", "rash", "diarrhea", "dizziness", "appetite loss", "sleep problems"];
export default function Signals() {
  const [trial, setTrial] = useState(null); const [s, setS] = useState(null);
  useEffect(() => { api.trials().then((t) => { if (t.length) { setTrial(t[0]); api.signals(t[0].id).then(setS); } }); }, []);
  if (!s) return <div className="card">Loading…</div>;
  return (<>
    <h2 style={{ margin: "4px 0 2px" }}>Signal watch</h2>
    <div className="muted" style={{ marginBottom: 12 }}>{trial?.name}. Counts, not conclusions. Every number traces back to the subjects behind it.</div>
    <div className="card"><h2>Severe self-reported symptom days per week <span className="muted small">(grade 3 or above, all subjects, from the continuous aggregate)</span></h2><WeeklyBars rows={s.diary_weekly} items={ITEMS} /></div>
    <div className="grid2">
      <div className="card"><h2>Flags by rule</h2><table><thead><tr><th>Rule</th><th>Severity</th><th>Fired</th><th>Open</th></tr></thead>
        <tbody>{s.flag_rules.map((r, i) => <tr key={i}><td>{r.rule}</td><td><Sev s={r.severity} /></td><td>{r.n}</td><td>{r.open}</td></tr>)}</tbody></table>
        <div className="muted small" style={{ marginTop: 6 }}><Link to={`/trials/${trial.id}`}>Open the study</Link> to see which subjects.</div></div>
      <div className="card"><h2>Most recorded adverse events</h2><table><thead><tr><th>Event</th><th>Count</th><th>Serious</th></tr></thead>
        <tbody>{s.top_events.map((e, i) => <tr key={i}><td>{e.pt}</td><td>{e.n}</td><td>{e.serious || ""}</td></tr>)}</tbody></table></div>
    </div>
  </>);
}
