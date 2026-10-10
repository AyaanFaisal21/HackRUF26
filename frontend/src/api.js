const j = (r) => { if (!r.ok) throw new Error(r.statusText); return r.json(); };
export const getQueue = () => fetch("/api/queue").then(j);
export const getStats = () => fetch("/api/stats").then(j);
export const getCase = (id) => fetch(`/api/cases/${id}`).then(j);
export const getHistory = (id) => fetch(`/api/cases/${id}/history`).then(j);
export const decideDuplicate = (id, other, merge) =>
  fetch(`/api/cases/${id}/duplicates`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ other_case_id: other, merge }) }).then(j);
export const confirmField = (id, field, value) =>
  fetch(`/api/cases/${id}/fields`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ field, value }) }).then(j);
