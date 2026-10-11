const CONF = { likely: "green", possible: "amber", unclear: "" };
export function Diagnosis({ dx, onApply, compact, applyLabel }) {
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
export function ModelSuggestion({ s, model }) {
  return (<div className="small">
    <div><span className={`pill ${CONF[s.confidence] ?? ""}`}>{s.confidence}</span> {s.likely_cause}</div>
    <div style={{ marginTop: 4 }}><b>Suggested decision.</b> {s.suggested_decision}</div>
    <div className="muted">Verify with {s.verify_with}. <span>({model})</span></div>
  </div>);
}
