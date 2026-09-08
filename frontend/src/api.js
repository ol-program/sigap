const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

// Token & handler 401 di-set dari AuthContext (bukan disimpan di sini) --
// modul ini tetap bisa dites/dipakai tanpa React. Lihat AuthContext.jsx.
let authToken = null;
let onUnauthorized = () => {};
let onMustChangePassword = () => {};

export function setAuthToken(token) {
  authToken = token;
}

export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn;
}

// Dipanggil kalau server balas 403 MUST_CHANGE_PASSWORD (bisa terjadi
// meski session lokal belum tahu, mis. admin reset password dari tab lain).
export function setMustChangePasswordHandler(fn) {
  onMustChangePassword = fn;
}

async function request(method, path, { params, body } = {}) {
  const url = new URL(BASE_URL + path);
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, v);
    });
  }
  const headers = { "Content-Type": "application/json" };
  if (authToken) headers.Authorization = `Bearer ${authToken}`;

  const res = await fetch(url, {
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

  if (res.status === 403 && payload?.detail?.code === "MUST_CHANGE_PASSWORD") {
    onMustChangePassword();
  }

  if (!res.ok) {
    const detail = payload?.detail;
    const message = typeof detail === "string" ? detail : detail?.message || `Gagal memuat ${path} (${res.status})`;
    const err = new Error(message);
    err.status = res.status;
    err.code = typeof detail === "object" ? detail.code : undefined;
    throw err;
  }
  return payload;
}

const get = (path, params) => request("GET", path, { params });

export const api = {
  login: (username, password) => request("POST", "/auth/login", { body: { username, password } }),
  changePassword: (passwordLama, passwordBaru) =>
    request("POST", "/auth/change-password", { body: { password_lama: passwordLama, password_baru: passwordBaru } }),
  ringkasan: (periode) => get("/ringkasan", { periode }),
  koperasiList: (params) => get("/koperasi", params),
  koperasiDetail: (id) => get(`/koperasi/${id}`),
  notifikasi: (params) => get("/notifikasi", params),
  insight: (id) => get(`/insight/${id}`),
  wilayah: () => get("/wilayah"),
  petaProvinsi: (params) => get("/peta/provinsi", params),
  petaKabupaten: (params) => get("/peta/kabupaten", params),
  metodologi: () => get("/metodologi"),
  // Endpoint /admin/users/* (manajemen akun) dipakai dari frontend-admin/, bukan di sini.
};
