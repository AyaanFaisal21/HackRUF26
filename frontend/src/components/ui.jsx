import React from "react";
export const fmtDate = (d) => (d ? new Date(d).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" }) : "");
export const fmtDT = (d) => (d ? new Date(d).toLocaleString() : "");
const VERDICT = { agree: ["green", "agree"], single_source: ["blue", "single source"], disagree: ["red", "disagree"], rule_fail: ["red", "check failed"], missing: ["amber", "missing"], empty: ["muted", "empty"] };
export const Verdict = ({ v }) => { const [c, t] = VERDICT[v] ?? ["muted", v ?? "—"]; return <span className={`pill ${c}`}>{t}</span>; };
export const Status = ({ s }) => <span className={`pill ${s === "signed" ? "green" : s === "in_review" ? "blue" : s === "read" ? "green" : s === "failed" ? "red" : ""}`}>{s?.replace("_", " ")}</span>;
export const Org = ({ o }) => <span className={`pill ${/Hospital|Pediatrics/.test(o ?? "") ? "blue" : "amber"}`}>{o}</span>;
export const Stat = ({ n, label, warn }) => <div className="stat"><b style={{ color: warn ? "var(--red)" : undefined }}>{n ?? "–"}</b><span>{label}</span></div>;
export const Conf = ({ c }) => c == null ? null : <span className="muted small">{Math.round(c * 100)}%</span>;
export function Highlight({ text, spans, active }) {
  const ss = (spans || []).filter((s) => s.span_start != null).sort((a, b) => a.span_start - b.span_start);
  const pages = text.split("\f"); let offset = 0; const out = [];
  pages.forEach((page, pi) => {
    const parts = []; let i = 0;
    ss.filter((s) => s.span_start >= offset && s.span_start < offset + page.length).forEach((s, k) => {
      const a = s.span_start - offset, b = Math.min(s.span_end - offset, page.length);
      if (a < i) return;
      parts.push(page.slice(i, a)); parts.push(<mark key={k} className={active && active === s.id ? "active" : ""} id={`fact-${s.id}`} title={s.display}>{page.slice(a, b)}</mark>); i = b;
    });
    parts.push(page.slice(i));
    out.push(<div key={pi} className="page"><div className="pagehdr">page {pi + 1}</div><pre className="body">{parts}</pre></div>);
    offset += page.length + 1;
  });
  return <>{out}</>;
}
