import React, { useEffect, useState } from "react";
import { BrowserRouter, Routes, Route, NavLink, Navigate } from "react-router-dom";
import { api } from "./api.js";
import Patients from "./pages/Patients.jsx";
import Patient from "./pages/Patient.jsx";
import FormReview from "./pages/FormReview.jsx";
import Queue from "./pages/Queue.jsx";
import Documents from "./pages/Documents.jsx";
import DocumentView from "./pages/DocumentView.jsx";
import Metrics from "./pages/Metrics.jsx";

function Layout({ children }) {
  const [health, setHealth] = useState(null);
  useEffect(() => { api.health().then(setHealth).catch(() => setHealth({ ok: false })); }, []);
  return (<>
    <header className="top">
      <span className="brand">Sourced<small>forms that fill themselves, with receipts</small></span>
      <nav><NavLink to="/patients">Patients</NavLink><NavLink to="/queue">Review queue</NavLink><NavLink to="/documents">Documents</NavLink><NavLink to="/metrics">Metrics</NavLink></nav>
      <span className="right">{health ? (health.ok ? `api ok · reader: ${health.model ?? "none, deterministic mode"}` : "api unreachable") : ""}</span>
    </header>
    <main>{children}</main>
  </>);
}

export default function App() {
  return (
    <BrowserRouter><Layout><Routes>
      <Route path="/" element={<Navigate to="/patients" replace />} />
      <Route path="/patients" element={<Patients />} />
      <Route path="/patients/:id" element={<Patient />} />
      <Route path="/forms/:id" element={<FormReview />} />
      <Route path="/queue" element={<Queue />} />
      <Route path="/documents" element={<Documents />} />
      <Route path="/documents/:id" element={<DocumentView />} />
      <Route path="/metrics" element={<Metrics />} />
    </Routes></Layout></BrowserRouter>);
}
