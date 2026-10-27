const BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");
async function getJson(path) {
  const response = await fetch(`${BASE}${path}`);
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try { const body = await response.json(); if (body.detail) message = body.detail; } catch {}
    throw new Error(message);
  }
  return response.json();
}
const query = (from, to, cutoff) => new URLSearchParams({ from, to, cutoff_hour: String(cutoff) });
export const getOverview = (from, to, cutoff) => getJson(`/api/forecast/overview?${query(from, to, cutoff)}`);
export const getSeries = (from, to, cutoff) => getJson(`/api/forecast/series?${query(from, to, cutoff)}`);
export const getAccuracy = (from, to, cutoff) => getJson(`/api/forecast/accuracy?${query(from, to, cutoff)}`);
export const getHistory = (start) => getJson(`/api/forecast/history?${new URLSearchParams({ start_time: start })}`);
