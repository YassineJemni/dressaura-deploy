const API_URL = "https://dressaura-backend.vercel.app";

export async function fetchDresses() {
  const res = await fetch(`${API_URL}/dresses/`);
  if (!res.ok) {
    throw new Error("Failed to fetch dresses");
  }
  return res.json();
}
