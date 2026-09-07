const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

// Sama seperti frontend/src/api.js (token & handler di-set dari luar, lihat
// App.jsx) TAPI dipangkas -- app ini cuma butuh login, ganti password, &
// endpoint /admin/users/*. TIDAK ada endpoint data koperasi di sini SAMA
// SEKALI -- superadmin memang tidak boleh melihatnya (lihat
// get_superadmin_user & scope_clause di backend/auth/auth.py).
let authToken = null;
let onUnauthorized = () => {};

export function setAuthToken(token) {
  authToken = token;
}

export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn;
}

async function request(method, path, { body } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (authToken) headers.Authorization = `Bearer ${authToken}`;

  const res = await fetch(BASE_URL + path, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (res.status === 401) {
    onUnauthorized();
  }

  const text = await res.text();
  let payload = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = null;
    }
  }

  if (!res.ok) {
    const detail = payload?.detail;
    const message = typeof detail === "string" ? detail : detail?.message || `Gagal memuat ${path} (${res.status})`;
    const err = new Error(message);
    err.status = res.status;
    throw err;
  }
  return payload;
}

export const api = {
  login: (username, password) => request("POST", "/auth/login", { body: { username, password } }),
  changePassword: (passwordLama, passwordBaru) =>
    request("POST", "/auth/change-password", { body: { password_lama: passwordLama, password_baru: passwordBaru } }),
  adminListKabupaten: () => request("GET", "/admin/kabupaten"),
  adminListUsers: () => request("GET", "/admin/users"),
  adminCreateUser: (body) => request("POST", "/admin/users", { body }),
  adminUpdateUser: (username, body) => request("PUT", `/admin/users/${username}`, { body }),
  adminResetPassword: (username, passwordBaru) =>
    request("POST", `/admin/users/${username}/reset-password`, { body: { password_baru: passwordBaru } }),
  adminDeleteUser: (username) => request("DELETE", `/admin/users/${username}`),
  getAiKey: () => request("GET", "/admin/ai-key"),
  setAiKey: (apiKey) => request("PUT", "/admin/ai-key", { body: { api_key: apiKey } }),
  setAiProvider: (provider) => request("PUT", "/admin/ai-provider", { body: { provider } }),
  setAiModel: (model) => request("PUT", "/admin/ai-model", { body: { model } }),
};
