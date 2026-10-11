import React, { useEffect, useState } from "react";
import { BrowserRouter, Routes, Route, NavLink, Navigate } from "react-router-dom";
import { api } from "./api.js";
import Trials from "./pages/Trials.jsx";
import Trial from "./pages/Trial.jsx";
import Patient from "./pages/Patient.jsx";
import Intake from "./pages/Intake.jsx";
import FdaQueue from "./pages/FdaQueue.jsx";
import FdaForm from "./pages/FdaForm.jsx";
import Signals from "./pages/Signals.jsx";

function Layout({ children }) {
  const [health, setHealth] = useState(null);
  useEffect(() => { api.health().then(setHealth).catch(() => setHealth({ ok: false })); }, []);
  return (<>
    <header className="top">
      <span className="brand">Day Zero</span>
      <nav>
        <NavLink to="/trials">Trials</NavLink><NavLink to="/intake">Intake</NavLink><NavLink to="/fda">FDA queue</NavLink><NavLink to="/signals">Signals</NavLink>
      </nav>
      <span className="right">{health ? (health.ok ? `api ok · model: ${health.llm ?? "none (deterministic mode)"}` : "api unreachable") : ""}</span>
    </header>
    <main>{children}</main>
  </>);
}

export default function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Navigate to="/trials" replace />} />
          <Route path="/trials" element={<Trials />} />
          <Route path="/trials/:id" element={<Trial />} />
          <Route path="/patients/:id" element={<Patient />} />
          <Route path="/intake" element={<Intake />} />
          <Route path="/intake/:id" element={<Intake />} />
          <Route path="/fda" element={<FdaQueue />} />
          <Route path="/fda/:id" element={<FdaForm />} />
          <Route path="/signals" element={<Signals />} />
        </Routes>
      </Layout>
    </BrowserRouter>);
}
