import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api.js";
import { FactsOverTime } from "../components/charts.jsx";

function Ecg() {
  // the monitor trace: one beat, repeated; drawn by animating the dash offset, with a fading echo behind the bright head
  const beat = "l40 0 l6 -6 l6 6 l8 0 l4 -34 l6 70 l5 -36 l6 0 l8 0 l10 -10 l10 10 l35 0";
  const d = "M -200 100 " + Array.from({ length: 14 }, () => beat).join(" ");
  return (<svg className="ecg" viewBox="0 0 1600 200" preserveAspectRatio="none" aria-hidden="true">
    <path className="ecg-grid" d={Array.from({ length: 9 }, (_, i) => `M0 ${i * 25} H1600`).join(" ") + Array.from({ length: 33 }, (_, i) => `M${i * 50} 0 V200`).join(" ")} />
    <path className="ecg-echo" d={d} />
    <path className="ecg-line" d={d} />
  </svg>);
}

export default function Home() {
  const [stats, setStats] = useState(null); const [demo, setDemo] = useState({}); const [series, setSeries] = useState([]); const nav = useNavigate();
  useEffect(() => {
    api.stats().then(setStats).catch(() => {}); api.factsDaily().then(setSeries).catch(() => {});
    api.patients().then((ps) => setDemo((d) => ({ ...d, patient: ps.find((p) => p.n_documents > 0 && p.kind === "adult")?.id, child: ps.find((p) => p.kind === "child")?.id }))).catch(() => {});
    api.queue().then((q) => setDemo((d) => ({ ...d, form: q.find((r) => r.unresolved > 0 && r.form_id !== "nj_ch14")?.id ?? q[0]?.id }))).catch(() => {});
  }, []);
  const patientTo = demo.patient ? `/patients/${demo.patient}` : "/patients", formTo = demo.form ? `/forms/${demo.form}` : "/queue";
  return (<div className="land">
    <Ecg />
    <section className="band">
      <div className="eyebrow">Clinical trial sites · sponsors · any clinician with a stack of forms</div>
      <h1>Clinical data that manages itself, <span>with receipts.</span></h1>
      <p>Sourced reads every record, structured or on paper, moves the facts where they are needed, flags what disagrees, and keeps a receipt on every value. We cover the unglamorous plumbing and make sure people stay in the loop.</p>
      <div className="ctas">
        <button className="primary" disabled={!demo.form} onClick={() => nav(formTo)}>review a flagged form</button>
        <button disabled={!demo.patient} onClick={() => nav(patientTo)}>open a documented patient</button>
        <button disabled={!demo.child} onClick={() => nav(`/patients/${demo.child}`)}>open a school health form</button>
      </div>
      {stats && <div className="bigstats">
        <div><b>{stats.patients}</b><span>patients</span></div>
        <div><b>{stats.facts?.toLocaleString()}</b><span>facts with receipts</span></div>
        <div><b>{stats.sources}</b><span>source organizations</span></div>
        <div><b>{stats.documents_read}</b><span>documents read</span></div>
        <div><b>{stats.forms}</b><span>forms filled</span></div>
      </div>}
    </section>

    <section className="sec">
      <h2>The problem</h2>
      <div className="nums">
        <div><b>290,000</b><span>data points retyped by hand in one 400-patient trial.</span></div>
        <div><b>15 to 30%</b><span>of the trial's cost is checking that typing against the source.</span></div>
        <div><b>17%</b><span>reach the database through structured connectors. The rest is faxes and notes.</span></div>
      </div>
      <div className="fine">Sources: PMC4386950 for the cost share; TransFAIR, PMC10277109 for the 17 percent. The first number is 400 patients, 12 visits, 60 fields.</div>
    </section>

    <section className="sec">
      <h2>How it works</h2>
      <div className="how">
        <Link to={patientTo}><i>01</i><b>Read</b><span>Hospital records and outside faxes become facts, each with its page, its quote, or its record id.</span><em>see a patient</em></Link>
        <Link to={formTo}><i>02</i><b>Fill</b><span>Pick a form and a visit. Every field fills from the ledger with a receipt.</span><em>see a form</em></Link>
        <Link to="/queue"><i>03</i><b>Verify</b><span>A second pass checks the range, the quote, and agreement between sources. Disagreements are flagged.</span><em>see the queue</em></Link>
        <Link to={formTo}><i>04</i><b>Sign</b><span>The coordinator decides the flagged fields, signs, and exports with the audit trail.</span><em>see the export</em></Link>
      </div>
    </section>

    <section className="sec">
      <h2>When two sources disagree</h2>
      <div className="proto">
        <div><i>1</i><span>Flagged, not guessed.</span></div>
        <div><i>2</i><span>Both receipts, side by side.</span></div>
        <div><i>3</i><span>Why, in plain words.</span></div>
        <div><i>4</i><span>A decision with a reason.</span></div>
        <div><i>5</i><span>All of it in the audit trail.</span></div>
      </div>
    </section>

    <section className="sec">
      <h2>Who uses it</h2>
      <div className="who">
        <div><b>Study coordinator</b><span>fills the visit forms and signs.</span></div>
        <div><b>Monitor</b><span>verifies by receipt, not by site visit.</span></div>
        <div><b>Data manager</b><span>receives ODM records with provenance attached.</span></div>
        <div><b>Any clinician with forms</b><span>school physicals, camp and sports forms, referrals, prior authorizations, disability paperwork. The school health record is our example.</span></div>
      </div>
    </section>

    <section className="sec motto">
      <p>The model reads. The rules fill and check. The human signs.</p>
      <div className="chips"><span className="chip">FHIR R4</span><span className="chip">LOINC</span><span className="chip">CDASH forms</span><span className="chip">ODM export</span><span className="chip">Tiger Data</span></div>
    </section>

    {series.length > 0 && <section className="sec last"><h2>Live ledger on Tiger Data</h2><FactsOverTime rows={series} /></section>}
  </div>);
}
