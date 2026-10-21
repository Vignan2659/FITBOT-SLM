// Thin fetch wrapper for the FitBot FastAPI backend.
const BASE = import.meta.env.VITE_API_URL || "/api";
const TOKEN_KEY = "fitbot_token";

export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage unavailable (private mode) - session lasts until reload */
  }
}

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

let onUnauthorized = () => {};
export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn;
}

async function request(path, { method = "GET", body, auth = true } = {}) {
  const headers = { "Content-Type": "application/json" };
  const token = getToken();
  if (auth && token) headers.Authorization = `Bearer ${token}`;
  let res;
  try {
    res = await fetch(`${BASE}${path}`, { method, headers, body: body ? JSON.stringify(body) : undefined });
  } catch {
    throw new ApiError(0, "Cannot reach the FitBot server. Is the backend running on port 8000?");
  }
  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    if (res.status === 401 && auth && token) onUnauthorized();
    let msg = data.detail || `Request failed (${res.status})`;
    if (Array.isArray(msg)) msg = msg.map((d) => `${d.loc?.slice(-1)[0] ?? ""}: ${d.msg}`).join("; ");
    throw new ApiError(res.status, msg);
  }
  return data;
}

export const api = {
  register: (name, email, password) => request("/auth/register", { method: "POST", body: { name, email, password }, auth: false }),
  login: (email, password) => request("/auth/login", { method: "POST", body: { email, password }, auth: false }),
  me: () => request("/auth/me"),
  logout: () => request("/auth/logout", { method: "POST" }),
  getProfile: () => request("/auth/profile"),
  updateProfile: (profile) => request("/auth/profile", { method: "PUT", body: profile }),
  listConversations: () => request("/conversations"),
  createConversation: (title) => request("/conversations", { method: "POST", body: title ? { title } : {} }),
  getConversation: (id) => request(`/conversations/${id}`),
  deleteConversation: (id) => request(`/conversations/${id}`, { method: "DELETE" }),
  chat: (message, conversationId) => request("/chat", { method: "POST", body: { message, conversation_id: conversationId ?? null } }),
  exercises: (params = {}) => request(`/exercises?${new URLSearchParams(params)}`, { auth: false }),
  health: () => request("/health", { auth: false }),
  yogaPoses: (params = {}) => request(`/yoga/poses?${new URLSearchParams(params)}`, { auth: false }),
  yogaPose: (slug) => request(`/yoga/poses/${encodeURIComponent(slug)}`, { auth: false }),
  yogaFilters: () => request("/yoga/filters", { auth: false }),
  yogaRoutine: (params = {}) => request(`/yoga/routine?${new URLSearchParams(params)}`, { auth: false }),
  rateMessage: (id, rating) => request(`/messages/${id}/feedback`, { method: "PUT", body: { rating } }),
  savePlan: (plan) => request("/plans", { method: "POST", body: { plan } }),
  listPlans: () => request("/plans"),
  deletePlan: (id) => request(`/plans/${id}`, { method: "DELETE" }),
  logWorkouts: (entries) => request("/workouts", { method: "POST", body: entries }),
  listWorkouts: (limit = 50) => request(`/workouts?limit=${limit}`),
  deleteWorkout: (id) => request(`/workouts/${id}`, { method: "DELETE" }),
  workoutStats: (today) => request(`/workouts/stats?${new URLSearchParams({ today, weeks: 8 })}`),
};

// Local calendar date as YYYY-MM-DD (not UTC, so late-evening workouts land on the right day).
export function localDate(d = new Date()) {
  const z = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${z(d.getMonth() + 1)}-${z(d.getDate())}`;
}
