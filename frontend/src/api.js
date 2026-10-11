const j = async (r) => { if (!r.ok) throw new Error(`${r.status} ${await r.text()}`); return r.json(); };
const post = (url, body) => fetch(url, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body ?? {}) }).then(j);
export const api = {
  health: () => fetch("/api/health").then(j),
  queue: () => fetch("/api/queue").then(j),
  stats: () => fetch("/api/stats").then(j),
  intake: () => fetch("/api/stats/intake").then(j),
  case: (id) => fetch(`/api/cases/${id}`).then(j),
  history: (id) => fetch(`/api/cases/${id}/history`).then(j),
  decideDuplicate: (id, other, merge) => post(`/api/cases/${id}/duplicates`, { other_case_id: other, merge }),
  caseForm: (id) => post(`/api/cases/${id}/form`),
  trials: () => fetch("/api/trials").then(j),
  trial: (id) => fetch(`/api/trials/${id}`).then(j),
  signals: (id) => fetch(`/api/trials/${id}/signals`).then(j),
  subject: (id) => fetch(`/api/subjects/${id}`).then(j),
  decideFlag: (id, status, actor) => post(`/api/flags/${id}`, { status, actor }),
  brief: (id, narrative) => post(`/api/subjects/${id}/brief?narrative=${narrative ? "true" : "false"}`),
  sign: (briefId, a) => post(`/api/briefs/${briefId}/sign`, a),
  fda: () => fetch("/api/fda").then(j),
  form: (id) => fetch(`/api/fda/${id}`).then(j),
  verify: (id, fields, actor) => post(`/api/fda/${id}/verify`, { fields, actor }),
  submit: (id) => post(`/api/fda/${id}/submit`),
};
