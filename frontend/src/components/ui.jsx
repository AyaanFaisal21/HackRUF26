import React from "react";
export const Sev = ({ s }) => <span className={`pill ${s === "urgent" ? "red" : s === "review" ? "amber" : "blue"}`}>{s}</span>;
export const Clock = ({ expedited, daysLeft, clock }) => {
  if (!expedited && clock == null) return <span className="pill muted">no clock</span>;
  if (daysLeft == null) return <span className="pill muted">no clock</span>;
  if (daysLeft < 0) return <span className="pill red">overdue {-daysLeft}d</span>;
  if (daysLeft <= 2) return <span className="pill red">{daysLeft}d left</span>;
  if (daysLeft <= 5) return <span className="pill amber">{daysLeft}d left</span>;
  return <span className="pill green">{daysLeft}d left</span>;
};
export const Status = ({ s }) => <span className={`pill ${s === "submitted" ? "green" : s === "verified" ? "blue" : s === "confirmed" ? "green" : s === "dismissed" ? "muted" : ""}`}>{s}</span>;
export const Stat = ({ n, label, warn }) => <div className="stat"><b style={{ color: warn ? "var(--red)" : undefined }}>{n ?? "–"}</b><span>{label}</span></div>;
export function LogicChain({ flag, onDecide }) {
  const [open, setOpen] = React.useState(flag.severity === "urgent");
  return (
    <div className={`flag ${flag.severity}`}>
      <div style={{ display: "flex", gap: 8, alignItems: "baseline", flexWrap: "wrap" }}>
        <Sev s={flag.severity} /><b>{flag.title}</b><span className="muted small">{flag.rule} · {flag.fired_on ?? "trial-level"} · {flag.id}</span>
        <span style={{ marginLeft: "auto" }}><Status s={flag.status} /> <button onClick={() => setOpen(!open)}>{open ? "hide" : "why?"}</button></span>
      </div>
      {open && (<>
        <ol className="logic">{flag.logic.map((l, i) => <li key={i}>{l}</li>)}</ol>
        <div className="muted small" style={{ marginTop: 6 }}>§ {flag.citation}</div>
        {onDecide && flag.status === "open" && <div style={{ marginTop: 8 }}><button className="primary" onClick={() => onDecide(flag.id, "confirmed")}>confirm as event</button> <button onClick={() => onDecide(flag.id, "dismissed")}>dismiss</button></div>}
      </>)}
    </div>);
}
export const fmtDate = (d) => (d ? new Date(d).toLocaleDateString(undefined, { month: "short", day: "numeric" }) : "");
export const fmtDT = (d) => (d ? new Date(d).toLocaleString() : "");
