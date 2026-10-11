import React from "react";
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, Legend, ReferenceLine, CartesianGrid, BarChart, Bar } from "recharts";
import { fmtDate } from "./ui.jsx";
const COLORS = ["#1d4ed8", "#b91c1c", "#15803d", "#b45309", "#7c3aed", "#0e7490", "#be185d", "#4b5563"];

export function SymptomChart({ diaries, items }) {
  const byDate = {};
  diaries.forEach((d) => { (byDate[d.date] ||= { date: d.date })[d.item] = d.grade; });
  const data = Object.values(byDate).sort((a, b) => (a.date < b.date ? -1 : 1));
  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={data} margin={{ top: 6, right: 12, left: -18, bottom: 0 }}>
        <CartesianGrid stroke="#eee" /><XAxis dataKey="date" tickFormatter={fmtDate} minTickGap={28} fontSize={11} /><YAxis domain={[0, 4]} ticks={[0, 1, 2, 3, 4]} fontSize={11} />
        <Tooltip labelFormatter={fmtDate} /><Legend wrapperStyle={{ fontSize: 12 }} />
        <ReferenceLine y={3} stroke="#b91c1c" strokeDasharray="4 4" />
        {items.map((it, i) => <Line key={it} type="stepAfter" dataKey={it} stroke={COLORS[i % COLORS.length]} dot={false} strokeWidth={1.6} isAnimationActive={false} />)}
      </LineChart>
    </ResponsiveContainer>);
}

export function LabChart({ labs, tests = ["ALT", "AST", "BILI", "ALP"] }) {
  const byDate = {};
  labs.forEach((l) => { if (tests.includes(l.test)) (byDate[l.date] ||= { date: l.date })[l.test] = l.x_uln; });
  const data = Object.values(byDate).sort((a, b) => (a.date < b.date ? -1 : 1));
  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={data} margin={{ top: 6, right: 12, left: -18, bottom: 0 }}>
        <CartesianGrid stroke="#eee" /><XAxis dataKey="date" tickFormatter={fmtDate} minTickGap={28} fontSize={11} /><YAxis fontSize={11} label={{ value: "x ULN", angle: -90, position: "insideLeft", fontSize: 11 }} />
        <Tooltip labelFormatter={fmtDate} /><Legend wrapperStyle={{ fontSize: 12 }} />
        <ReferenceLine y={3} stroke="#b91c1c" strokeDasharray="4 4" label={{ value: "3x ULN", fontSize: 10, position: "right" }} />
        <ReferenceLine y={2} stroke="#b45309" strokeDasharray="4 4" label={{ value: "2x", fontSize: 10, position: "right" }} />
        {tests.map((t, i) => <Line key={t} type="monotone" dataKey={t} stroke={COLORS[i]} strokeWidth={1.8} isAnimationActive={false} connectNulls />)}
      </LineChart>
    </ResponsiveContainer>);
}

export function WeeklyBars({ rows, items }) {
  const byWeek = {};
  rows.forEach((r) => { (byWeek[r.week] ||= { week: r.week })[r.item] = r.n_severe; });
  const data = Object.values(byWeek).sort((a, b) => (a.week < b.week ? -1 : 1));
  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={data} margin={{ top: 6, right: 12, left: -18, bottom: 0 }}>
        <CartesianGrid stroke="#eee" /><XAxis dataKey="week" tickFormatter={fmtDate} fontSize={11} /><YAxis fontSize={11} /><Tooltip labelFormatter={fmtDate} /><Legend wrapperStyle={{ fontSize: 12 }} />
        {items.map((it, i) => <Bar key={it} dataKey={it} stackId="a" fill={COLORS[i % COLORS.length]} isAnimationActive={false} />)}
      </BarChart>
    </ResponsiveContainer>);
}
