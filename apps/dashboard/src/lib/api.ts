const API_BASE = "http://localhost:3000";

export async function fetchAPI(path: string) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function search(q: string) {
  return fetchAPI(`/api/search?q=${encodeURIComponent(q)}`);
}

export async function getCompanies() {
  return fetchAPI("/api/companies");
}

export async function getCompany(id: string) {
  return fetchAPI(`/api/companies/${id}`);
}

export async function getSignals(params?: { source?: string; limit?: number }) {
  const qs = new URLSearchParams();
  if (params?.source) qs.append("source", params.source);
  if (params?.limit) qs.append("limit", String(params.limit));
  return fetchAPI(`/api/signals?${qs}`);
}

export async function getEvents(params?: { type?: string; limit?: number }) {
  const qs = new URLSearchParams();
  if (params?.type) qs.append("type", params.type);
  if (params?.limit) qs.append("limit", String(params.limit));
  return fetchAPI(`/api/events?${qs}`);
}

export async function getFunding() {
  return fetchAPI("/api/funding");
}

export async function getStatus() {
  return fetchAPI("/api/status");
}
