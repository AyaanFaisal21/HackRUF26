import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { Stat } from "../components/ui.jsx";

export default function Trials() {
  const [trials, setTrials] = useState([]);
  useEffect(() => { api.trials().then(setTrials); }, []);
  return (<>
    <h2 style={{ margin: "4px 0 14px" }}>Studies</h2>
    <div className="grid3">
      {trials.map((t) => (
        <Link key={t.id} to={`/trials/${t.id}`} className="card cardlink">
          <div className="muted small">{t.id} · phase {t.phase}</div>
          <div style={{ fontWeight: 600, margin: "4px 0 10px" }}>{t.name}</div>
          <div className="stats">
            <Stat n={t.n_subjects} label="subjects" /><Stat n={t.sites.length} label="sites" />
            <Stat n={t.open_flags} label="open flags" warn={t.urgent_flags > 0} /><Stat n={t.urgent_flags} label="urgent" warn={t.urgent_flags > 0} /><Stat n={t.forms_pending} label="forms to verify" />
          </div>
          <div className="muted small" style={{ marginTop: 10 }}>{t.product} · {t.source}</div>
        </Link>))}
    </div>
  </>);
}
