import { API_URL, apiFetch } from "./client";

export async function fetchDresses() {
  const res = await apiFetch(`${API_URL}/dresses/`);
  if (!res.ok) {
    throw new Error("Failed to fetch dresses");
  }
  return res.json();
}
