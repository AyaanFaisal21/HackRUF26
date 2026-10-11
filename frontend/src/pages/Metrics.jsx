import { useEffect, useState } from "react";
import { api } from "../api.js";
import { Stat } from "../components/ui.jsx";

const pct = (x) => (x == null ? "–" : `${Math.round(x * 100)}%`);
export default function Metrics() {
  const [m, setM] = useState(null); const [stats, setStats] = useState(null); const [busy, setBusy] = useState(false);
  const load = (refresh) => { setBusy(true); api.metrics(refresh).then(setM).finally(() => setBusy(false)); };
  useEffect(() => { load(false); api.stats().then(setStats); }, []);
  return (<>
    <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}><h2 style={{ margin: "4px 0 8px" }}>Metrics</h2><span className="muted">scored against the answer key</span><button style={{ marginLeft: "auto" }} onClick={() => load(true)} disabled={busy} title="re-run the evaluation against the live ledger; slow on a remote database">{busy ? "scoring…" : "recompute live"}</button></div>
    {stats && <div className="card"><h2>Ledger</h2><div className="stats"><Stat n={stats.patients} label="patients" /><Stat n={stats.facts?.toLocaleString()} label="facts" /><Stat n={stats.sources} label="source organizations" /><Stat n={stats.documents_read} label="documents read" /><Stat n={stats.forms_signed} label="forms signed" /><Stat n={stats.audit_events} label="audit events" /><Stat n={stats.facts_size} label="facts on disk" /><Stat n={stats.compression ? `${stats.compression.number_compressed_chunks}/${stats.compression.total_chunks}` : "–"} label="chunks compressed" /></div>
      <h3>Facts by source</h3><table><tbody>{stats.facts_by_source.map((r) => <tr key={r.source_org}><td>{r.source_org}</td><td>{r.n.toLocaleString()}</td></tr>)}</tbody></table></div>}
    {m ? (<>
      <div className="card"><h2>Forms</h2>
        <div className="stats"><Stat n={pct(m.fill_rate)} label="fields filled automatically" /><Stat n={pct(m.accuracy_of_filled)} label="accuracy of filled fields" /><Stat n={pct(m.receipt_coverage)} label="filled fields with a receipt" />
          <Stat n={`${m.planted_conflicts.caught}/${m.planted_conflicts.total}`} label="planted conflicts caught" /><Stat n={`${m.unit_traps.converted_correctly}/${m.unit_traps.total}`} label="unit traps converted" /><Stat n={`${m.gap_fills.filled_from_document}/${m.gap_fills.total}`} label="gaps filled from documents" />
          <Stat n={m.false_alarms} label="false alarms" warn={m.false_alarms > 0} /><Stat n={m.children_immunizations_complete} label="school forms complete across clinics" /></div>
        <div className="muted small" style={{ marginTop: 6 }}>{m.patients_scored} patients, {m.fields_with_truth} fields with a known truth. Reader: {m.reader_mode ?? "live"}. Computed {new Date(m.computed_at).toLocaleString()}.</div>
      </div>
      {m.reader && (<div className="card"><h2>Document reading: scripts baseline versus reader <span className="muted small">({m.reader.reader || "answer key"})</span></h2>
        <table><thead><tr><th>Document kind</th><th>Docs</th><th>Truth facts</th><th>Scripts recall</th><th>Scripts precision</th><th>Reader recall</th><th>Reader precision</th><th>Quotes not located</th></tr></thead>
          <tbody>{Object.entries(m.reader.by_kind).map(([k, r]) => <tr key={k} style={k === "all" ? { fontWeight: 600 } : {}}><td>{k.replace(/_/g, " ")}</td><td>{r.documents}</td><td>{r.truth}</td><td>{pct(r.scripts_recall)}</td><td>{pct(r.scripts_precision)}</td><td>{pct(r.reader_recall)}</td><td>{pct(r.reader_precision)}</td><td>{pct(r.unlocated_rate)}</td></tr>)}</tbody></table>
        <div className="muted small" style={{ marginTop: 6 }}>Scripts: hand-written label and value patterns for these layouts. They read tables; they do not read prose. Precision counts extras the reader found that the answer key does not list, such as a date of birth in a header.</div>
      </div>)}
      <div className="card"><h2>By concept</h2><table><thead><tr><th>Concept</th><th>Fields</th><th>Filled</th><th>Accuracy</th></tr></thead><tbody>{Object.entries(m.per_concept).map(([k, v]) => <tr key={k}><td>{k}</td><td>{v.n}</td><td>{v.filled}</td><td>{pct(v.accuracy)}</td></tr>)}</tbody></table></div>
    </>) : <div className="card muted">Scoring…</div>}
  </>);
}
