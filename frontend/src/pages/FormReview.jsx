import React, { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api.js";
import { Conf, Org, Status, Verdict, fmtDate, fmtDT } from "../components/ui.jsx";

const show = (v) => (v == null ? <i className="muted">blank</i> : String(v));
const detailText = (c, unit) => {
  if (typeof c.detail === "string") return c.detail;
  if (c.check === "cross_source" && c.detail && !Array.isArray(c.detail)) {
    const say = (x) => `${x.source} says ${x.value} ${unit ?? ""} (${x.days} day${x.days === 1 ? "" : "s"} from visit)`;
    return [...(c.detail.agree || []).map((x) => `agrees: ${say(x)}`), ...(c.detail.disagree || []).map((x) => `disagrees: ${say(x)}`)].join("; ") || "no other source in the window";
  }
  if (Array.isArray(c.detail)) return c.detail.map((r) => `${r.term}: ${Object.entries(r.conflicts).map(([k, v]) => `${k} ${v.join(" vs ")}`).join(", ")}`).join("; ");
  return JSON.stringify(c.detail);
};
function Receipt({ r }) {
  if (!r) return <span className="muted small">no source</span>;
  return (<span className="rcpt"><Org o={r.source_org} />{r.document_id ? <Link to={`/documents/${r.document_id}#fact-${r.id}`}>{r.document_id} p.{r.page}</Link> : <span>{r.resource_ref}</span>} · {fmtDate(r.observed_at)}</span>);
}

const CONF = { likely: "green", possible: "amber", unclear: "" };
function Diagnosis({ dx, onApply, compact, applyLabel }) {
  return (<div className={`dx ${compact ? "compact" : ""}`}>
    {!compact && <h3>Likely cause</h3>}
    <div className="small"><span className={`pill ${CONF[dx.confidence] ?? ""}`}>{dx.confidence}</span> {compact && <b>Likely cause. </b>}{dx.likely_cause}</div>
    {dx.evidence?.length > 0 && <ul className="small evidence">{dx.evidence.map((e, k) => <li key={k}>{e}</li>)}</ul>}
    {dx.suggestion ? <div className="small suggest"><b>Suggested decision.</b> {dx.suggestion.action === "choose" ? `Use ${dx.suggestion.value}: ` : "Keep the filled value: "}{dx.suggestion.reason}.
      {onApply && <> <button onClick={(e) => { e.stopPropagation(); onApply(dx.suggestion); }}>{applyLabel ?? "apply suggestion"}</button></>}</div>
      : <div className="small suggest muted">No suggestion: the receipts do not favor a value. The coordinator decides.</div>}
    {dx.verify_with && <div className="small muted">Verify with {dx.verify_with}.</div>}
  </div>);
}
function ModelSuggestion({ s, model }) {
  return (<div className="small">
    <div><span className={`pill ${CONF[s.confidence] ?? ""}`}>{s.confidence}</span> {s.likely_cause}</div>
    <div style={{ marginTop: 4 }}><b>Suggested decision.</b> {s.suggested_decision}</div>
    <div className="muted">Verify with {s.verify_with}. <span>({model})</span></div>
  </div>);
}

export default function FormReview() {
  const { id } = useParams();
  const [i, setI] = useState(null); const [sel, setSel] = useState(null); const [actor, setActor] = useState(""); const [manual, setManual] = useState(""); const [reason, setReason] = useState(""); const [msg, setMsg] = useState(null); const [hist, setHist] = useState([]); const [chain, setChain] = useState(null);
  const [open, setOpen] = useState({}); const [explaining, setExplaining] = useState(false);
  const askModel = (key) => { setExplaining(true); api.explain(id, key).then(load).catch((e) => setMsg(e.message)).finally(() => setExplaining(false)); };
  const load = () => { api.instance(id).then((x) => { setI(x); if (!sel) setSel(x.fields.find((f) => ["disagree", "rule_fail", "missing"].includes(f.verifier?.verdict) && !f.decision)?.key ?? x.fields[0]?.key); }); api.history(id).then(setHist); api.auditVerify().then(setChain).catch(() => {}); };
  useEffect(() => { load(); }, [id]);
  if (!i) return <div className="card">Loading…</div>;
  const f = i.fields.find((x) => x.key === sel);
  const unresolved = i.fields.filter((x) => ["disagree", "rule_fail", "missing"].includes(x.verifier?.verdict) && !x.decision).length;
  const act = (key, body) => api.decide(id, key, { ...body, actor: actor || "reviewer", reason: reason || body.reason }).then(() => { setMsg(null); setReason(""); load(); }).catch((e) => setMsg(e.message));
  const sign = () => api.sign(id, actor || "reviewer").then(() => { setMsg(null); load(); }).catch((e) => setMsg(e.message));
  const acceptClean = () => {
    const clean = i.fields.filter((x) => ["agree", "single_source"].includes(x.verifier?.verdict) && !x.decision && (x.value != null || x.rows?.length));
    clean.reduce((p, x) => p.then(() => api.decide(id, x.key, { action: "accept", actor: actor || "reviewer", reason: "no disagreement; accepted in bulk" })), Promise.resolve()).then(load).catch((e) => setMsg(e.message));
  };
  return (<>
    <div className="muted small"><Link to="/queue">Review queue</Link> › <Link to={`/patients/${i.patient_id}`}>{i.patient_id}</Link> › form #{i.id}</div>
    <div style={{ display: "flex", alignItems: "baseline", gap: 12, flexWrap: "wrap" }}>
      <h2 style={{ margin: "4px 0 8px" }}>{i.name} <span className="muted" style={{ fontWeight: 400 }}>{i.domain}</span></h2><Status s={i.status} />
      <span className="muted">{i.display_name} · visit {fmtDate(i.visit_date)} · filled in {i.filled_ms} ms · {i.n_filled}/{i.n_fields} fields filled</span>
      <span style={{ marginLeft: "auto" }}>{unresolved > 0 ? <span className="pill red">{unresolved} to resolve</span> : <span className="pill green">nothing unresolved</span>}</span>
    </div>
    <div className="card strip">
      {[["agree", "confirmed by two sources"], ["single_source", "one source"], ["disagree", "sources disagree"], ["rule_fail", "check failed"], ["missing", "missing"]].map(([v, l]) => { const n = i.fields.filter((x) => x.verifier?.verdict === v).length; return n ? <span key={v} className="stripitem"><Verdict v={v} /> {n} {l}</span> : null; })}
      <span className="muted small" style={{ marginLeft: "auto" }}>click a field to see its receipt</span>
    </div>
    <div className="grid2">
      <div className="card">
        {i.fields.map((x) => (
          <div key={x.key} className={`field ${sel === x.key ? "sel" : ""}`} onClick={() => setSel(x.key)}>
            <div className="lbl">{x.label}</div>
            <div className="val">{x.vtype === "list" ? <span>{(x.rows || []).length} row{(x.rows || []).length === 1 ? "" : "s"}{(x.rows || []).some((r) => Object.keys(r.conflicts || {}).length) && <span className="pill red" style={{ marginLeft: 6 }}>conflicts</span>}</span> : <><b>{show(x.value)}</b> <span className="muted">{x.value != null ? x.unit : ""}</span></>}
              {x.decision && <div className="muted small">decided: {x.decision.action}{x.decision.reason ? ` · ${x.decision.reason}` : ""}</div>}</div>
            <div><Verdict v={x.verifier?.verdict} /> <Conf c={x.vtype === "list" ? null : x.confidence} /></div>
            <div className="rcpt">{x.vtype === "list" ? <span className="muted small">{new Set((x.rows || []).flatMap((r) => r.sources.map((s) => s.source_org))).size} source(s)</span> : x.receipt ? <Org o={x.receipt.source_org} /> : <span className="muted small">no source</span>}</div>
          </div>))}
        <div style={{ display: "flex", gap: 10, alignItems: "center", marginTop: 12, flexWrap: "wrap" }}>
          <input placeholder="your name" value={actor} onChange={(e) => setActor(e.target.value)} />
          <button onClick={acceptClean} disabled={i.status === "signed"}>accept all unflagged</button>
          <button className="primary" disabled={i.status === "signed" || unresolved > 0 || !actor} onClick={sign}>sign and export</button>
          {i.status === "signed" && <a href={`/api/forms/instances/${i.id}/export`} target="_blank" rel="noreferrer">download export (ODM-shaped JSON)</a>}
          {msg && <span className="pill red">{msg}</span>}
        </div>
        <div className="muted small" style={{ marginTop: 6 }}>Signing requires a decision on every field the verifier flagged. Every decision is in the audit trail.</div>
      </div>
      <div className="sticky">
        {f && (<div className="card">
          <h2>{f.label}</h2>
          {f.vtype !== "list" ? (<>
            <div className="kv"><span className="muted">Filled value</span><span><b>{show(f.value)}</b> {f.value != null ? f.unit : ""} <Conf c={f.confidence} /></span>
              <span className="muted">Receipt</span><span><Receipt r={f.receipt} />{f.receipt?.quote && <div>“{f.receipt.quote}”</div>}{f.receipt?.attrs?.unit_as_written && f.receipt.attrs.unit_as_written !== f.unit && <div className="muted small">written as {f.receipt.attrs.as_written} {f.receipt.attrs.unit_as_written}, converted</div>}</span>
              <span className="muted">Verifier</span><span><Verdict v={f.verifier?.verdict} /> <span className="muted small">{f.verifier?.method}</span></span></div>
            {f.verifier?.explanation && (<><h3>Why it is flagged</h3><p className="small" style={{ margin: 0 }}>{f.verifier.explanation}</p></>)}
            {f.verifier?.diagnosis && <Diagnosis dx={f.verifier.diagnosis} onApply={i.status !== "signed" ? (sg) => act(f.key, sg.action === "choose" ? { action: "choose", fact_id: sg.fact_id, reason: `accepted suggestion: ${sg.reason}` } : { action: "accept", reason: `accepted suggestion: ${sg.reason}` }) : null} />}
            {(f.verifier?.model_suggestion || f.verifier?.model_explanation || ["disagree", "rule_fail"].includes(f.verifier?.verdict)) && (<><h3>Model's reading of the receipts</h3>
              {f.verifier?.model_suggestion ? <ModelSuggestion s={f.verifier.model_suggestion} model={f.verifier.model} />
                : f.verifier?.model_explanation ? <p className="small" style={{ margin: 0 }}>{f.verifier.model_explanation} <span className="muted">({f.verifier.model})</span></p>
                : <button onClick={() => askModel(f.key)} disabled={explaining}>{explaining ? "asking…" : "explain with the model"}</button>}</>)}
            <h3>Checks</h3>
            {(f.verifier?.checks || []).length ? <ul style={{ margin: "0 0 0 18px" }}>{f.verifier.checks.map((c, k) => <li key={k}><span className={`pill ${c.ok === false ? "red" : c.ok ? "green" : "muted"}`}>{c.check.replace(/_/g, " ")}</span> <span className="small">{detailText(c, f.unit)}</span></li>)}</ul> : <div className="muted small">No checks ran (no value).</div>}
            {f.alternatives?.length > 0 && (<><h3>Other values in the window</h3>{f.alternatives.map((a, k) => (
              <div key={k} className="alt"><b>{a.value}</b> {f.unit} <span className="muted small">· {a.days_from_visit} day(s) from visit</span> <Receipt r={a.receipt} />{a.receipt.quote && <div className="muted small">“{a.receipt.quote}”</div>}
                {i.status !== "signed" && <div style={{ marginTop: 4 }}><button onClick={() => act(f.key, { action: "choose", fact_id: a.receipt.id, reason: "chose alternative source" })}>use this value</button></div>}</div>))}</>)}
            {i.status !== "signed" && (<><h3>Decide</h3>
              <input placeholder="reason (goes in the audit trail)" value={reason} onChange={(e) => setReason(e.target.value)} style={{ width: "100%", marginBottom: 6 }} />
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
                <button className="primary" onClick={() => act(f.key, { action: "accept", reason: "confirmed against source" })} disabled={f.value == null}>accept</button>
                <input placeholder="manual value" value={manual} onChange={(e) => setManual(e.target.value)} style={{ width: 120 }} /><button onClick={() => act(f.key, { action: "manual", value: f.vtype === "number" ? Number(manual) : manual, reason: reason || "entered from source" })} disabled={!manual}>enter manually</button>
                <button onClick={() => act(f.key, { action: "blank", reason: reason || "not collected" })}>leave blank</button>
              </div></>)}
          </>) : (<>
            {(() => { const cols = Object.keys((f.rows || [])[0] || { term: 1 }).filter((k) => !["sources", "conflicts", "values", "n_sources", "name", "vaccine", "explanation", "diagnosis"].includes(k)); return (
            <table className="rows"><thead><tr>{cols.map((k) => <th key={k}>{k}</th>)}<th>sources</th></tr></thead>
              <tbody>{(f.rows || []).flatMap((r, k) => { const hasConflict = Object.keys(r.conflicts || {}).length > 0; const isOpen = open[k] ?? hasConflict; return [
                <tr key={k} className={`row ${hasConflict ? "conflict" : ""}`} onClick={() => setOpen({ ...open, [k]: !isOpen })}>{cols.map((c) => <td key={c}>{r[c] ?? ""}{r.conflicts?.[c] && <div className="small" style={{ color: "var(--red)" }}>sources disagree: {r.conflicts[c].join(" vs ")}</div>}</td>)}<td>{[...new Set(r.sources.map((s) => s.source_org))].map((o) => <Org key={o} o={o} />)}</td></tr>,
                isOpen ? <tr key={`${k}-d`} className="rowdetail"><td colSpan={cols.length + 1}>
                  {r.explanation && <div className="small" style={{ marginBottom: 6 }}><b>Why it is flagged.</b> {r.explanation}</div>}
                  {r.diagnosis && <Diagnosis dx={r.diagnosis} compact onApply={i.status !== "signed" && r.diagnosis.suggestion ? () => setReason(r.diagnosis.suggestion.reason) : null} applyLabel="use this reason" />}
                  {r.sources.map((s, j) => <div key={j} className="small"><Org o={s.source_org} />{s.document_id ? <Link to={`/documents/${s.document_id}#fact-${s.id}`} onClick={(e) => e.stopPropagation()}>{s.document_id} p.{s.page}</Link> : <span className="muted">{s.resource_ref}</span>} · {fmtDate(s.observed_at)}{s.attrs?.dose ? ` · ${s.attrs.dose}` : ""}{s.attrs?.end ? ` · ended ${String(s.attrs.end).slice(0, 10)}` : ""}{s.quote && <span className="quote"> · “{s.quote.replace(/\s+/g, " ").trim()}”</span>}</div>)}
                </td></tr> : null]; })}</tbody></table>); })()}
            {(f.rows || []).some((r) => Object.keys(r.conflicts || {}).length) && (<div style={{ marginTop: 8 }}>
              {f.verifier?.model_suggestion ? <div className="small"><b>Model's reading of the receipts.</b> <ModelSuggestion s={f.verifier.model_suggestion} model={f.verifier.model} /></div>
                : f.verifier?.model_explanation ? <p className="small" style={{ margin: 0 }}><b>Model's reading of the receipts.</b> {f.verifier.model_explanation} <span className="muted">({f.verifier.model})</span></p>
                : <button onClick={() => askModel(f.key)} disabled={explaining}>{explaining ? "asking…" : "explain with the model"}</button>}</div>)}
            {i.status !== "signed" && <div style={{ marginTop: 8 }}><input placeholder="reason" value={reason} onChange={(e) => setReason(e.target.value)} /> <button className="primary" onClick={() => act(f.key, { action: "accept", reason: reason || "rows reviewed" })}>accept rows as reviewed</button></div>}
          </>)}
        </div>)}
        <div className="card"><h3 style={{ marginTop: 0 }}>History</h3>
          {chain && <div className="small" style={{ marginBottom: 6 }}>{chain.intact ? <span className="pill green">chain intact</span> : <span className="pill red">chain broken at event {chain.first_broken_seq}</span>} <span className="muted">{chain.events} events in the audit log, each hashed with the one before it (SHA-256); head {String(chain.head).slice(0, 12)}…</span></div>}
          {hist.length ? <table><tbody>{hist.map((h, k) => <tr key={k}><td className="muted small">{fmtDT(h.at)}</td><td>{h.actor}</td><td className="small">{h.action.replace(/_/g, " ")}{h.field ? ` · ${h.field}` : ""}{h.reason ? ` · ${h.reason}` : ""}</td><td className="muted small" title={h.hash}>{h.hash ? h.hash.slice(0, 10) : ""}</td></tr>)}</tbody></table> : <div className="muted small">No actions yet.</div>}
        </div>
      </div>
    </div>
  </>);
}
