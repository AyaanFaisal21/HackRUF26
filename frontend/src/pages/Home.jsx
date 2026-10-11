import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api.js";
import { Stat } from "../components/ui.jsx";
import { FactsOverTime } from "../components/charts.jsx";

export default function Home() {
  const [stats, setStats] = useState(null); const [health, setHealth] = useState(null); const [demo, setDemo] = useState({}); const [series, setSeries] = useState([]); const nav = useNavigate();
  useEffect(() => {
    api.stats().then(setStats); api.health().then(setHealth); api.factsDaily().then(setSeries).catch(() => {});
    api.patients().then((ps) => setDemo((d) => ({ ...d, patient: ps.find((p) => p.n_documents > 0 && p.kind === "adult")?.id, child: ps.find((p) => p.kind === "child")?.id })));
    api.queue().then((q) => setDemo((d) => ({ ...d, form: q.find((r) => r.unresolved > 0 && r.form_id !== "nj_ch14")?.id ?? q[0]?.id })));
  }, []);
  return (<>
    <div className="hero">
      <h1>Medical forms that fill themselves, <span>with receipts.</span></h1>
      <p>Every trial visit produces data that someone retypes from the hospital record into the sponsor's forms, then someone else checks against the source. Sourced reads the records, including the faxes and notes no connector reaches, keeps every fact with its origin, fills the form, has a second pass check every field, and lets a human sign only what disagreed.</p>
      {stats && <div className="stats" style={{ marginTop: 14 }}><Stat n={stats.patients} label="patients" /><Stat n={stats.facts?.toLocaleString()} label="facts with receipts" /><Stat n={stats.sources} label="source organizations" /><Stat n={stats.documents_read} label="documents read" /><Stat n={stats.forms} label="forms filled" /></div>}
      <div className="muted small" style={{ marginTop: 8 }}>{health?.model ? `Document reader: ${health.model}` : "Document reader: answer key (no model key configured)"} · ledger on Tiger Data</div>
    </div>
    <div className="grid3">
      <div className="card"><h2>1. One patient, two clinics</h2><p className="small">A hospital record in FHIR and an outside clinic's faxes land in one ledger. Click a concept to see every value and where it came from, including a weight written in pounds and converted.</p>
        <button className="primary" disabled={!demo.patient} onClick={() => nav(`/patients/${demo.patient}`)}>open a documented patient</button></div>
      <div className="card"><h2>2. A form that filled itself</h2><p className="small">Each field carries a receipt and a verdict. The verifier caught a value that two sources disagree on. Pick, give a reason, sign, and download the export with the audit trail.</p>
        <button className="primary" disabled={!demo.form} onClick={() => nav(`/forms/${demo.form}`)}>review a flagged form</button></div>
      <div className="card"><h2>3. Same ledger, a school form</h2><p className="small">The New Jersey child health record fills from the same engine: immunizations unioned across two clinics, an urgent-care weight that disagrees with the pediatrician's.</p>
        <button className="primary" disabled={!demo.child} onClick={() => nav(`/patients/${demo.child}`)}>open a child's record</button></div>
    </div>
    {series.length > 0 && <div className="card"><h2>Facts arriving, by source <span className="muted small">(continuous aggregate on the ledger)</span></h2><FactsOverTime rows={series} /></div>}
    <div className="card"><h2>How it works</h2>
      <div className="steps">
        <div><b>Read</b><span>FHIR resources map deterministically. Documents are read by the model, which must quote every value verbatim; the quote is located to a page and span.</span></div>
        <div><b>Store</b><span>One fact per value: concept code, unit, when it was true, source organization, document page and span or resource id, extractor, confidence. Hypertable on Tiger.</span></div>
        <div><b>Fill</b><span>A form is a list of questions. Each is answered from the ledger, nearest to the visit first, with the other values it saw.</span></div>
        <div><b>Verify</b><span>Plausible range, the number in the quote matches the value, agreement across sources measured within three days, conflicts inside rows.</span></div>
        <div><b>Sign</b><span>Only flagged fields need a person. Every decision has a reason. The export is ODM-shaped and the audit trail is append-only.</span></div>
      </div>
      <div className="muted small" style={{ marginTop: 8 }}>The model reads. The rules fill and check. The human signs. <Link to="/metrics">Metrics</Link> scores it against the answer key, including a scripts baseline.</div>
    </div>
  </>);
}
