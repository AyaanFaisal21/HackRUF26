import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, Legend, CartesianGrid } from "recharts";
const COLORS = { "Memorial General Hospital": "#1d4ed8", "Riverside Clinic": "#b45309", "Riverside Diagnostics": "#d97706", "Sunrise Pediatrics": "#0e7490", "County Urgent Care": "#be185d" };
export function FactsOverTime({ rows }) {
  const byWeek = {};
  rows.forEach((r) => { const d = new Date(r.day); const wk = new Date(d.getFullYear(), d.getMonth(), d.getDate() - d.getDay()).toISOString().slice(0, 10); (byWeek[wk] ||= { week: wk })[r.source_org] = ((byWeek[wk] ||= {})[r.source_org] || 0) + Number(r.n); });
  const data = Object.values(byWeek).sort((a, b) => (a.week < b.week ? -1 : 1));
  const orgs = [...new Set(rows.map((r) => r.source_org))];
  const fmt = (d) => new Date(d).toLocaleDateString(undefined, { month: "short", day: "numeric" });
  return (
    <ResponsiveContainer width="100%" height={200}>
      <AreaChart data={data} margin={{ top: 6, right: 10, left: -18, bottom: 0 }}>
        <CartesianGrid stroke="#eee" /><XAxis dataKey="week" tickFormatter={fmt} fontSize={11} minTickGap={30} /><YAxis fontSize={11} /><Tooltip labelFormatter={fmt} /><Legend wrapperStyle={{ fontSize: 12 }} />
        {orgs.map((o) => <Area key={o} type="monotone" dataKey={o} stackId="1" stroke={COLORS[o] || "#6b7280"} fill={COLORS[o] || "#6b7280"} fillOpacity={0.25} isAnimationActive={false} />)}
      </AreaChart>
    </ResponsiveContainer>);
}
