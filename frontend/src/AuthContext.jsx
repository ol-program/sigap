import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { api, setAuthToken, setUnauthorizedHandler, setMustChangePasswordHandler } from "./api.js";

const STORAGE_KEY = "sigap_auth";
const AuthContext = createContext(null);

// Token JWT disimpan di localStorage -- pragmatis untuk tool internal ini,
// TAPI ini rentan XSS dibanding httpOnly cookie (JS yang berjalan di
// halaman bisa membaca localStorage). Kalau dashboard ini nanti memuat
// script pihak ketiga apa pun, pindahkan penyimpanan token ke httpOnly
// cookie + endpoint CSRF di backend -- di luar scope perbaikan saat ini.
function loadStored() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

// authToken di api.js di-set SINKRON di sini (bukan lewat useEffect di
// AuthProvider) -- dulu di-set via effect, dan effect baru jalan SETELAH
// commit + child mount, jadi halaman yang me-render tepat setelah login
// (mis. Ringkasan) sempat fetch dengan token kosong, dapat 401, lalu
// onUnauthorized() men-logout user itu juga PADAHAL login-nya sendiri
// sukses -- balik ke /login walau kredensialnya benar. Set token di titik
// yang sama dengan perubahan state (login/logout/initial load) memastikan
// tidak ada request yang berangkat sebelum token terpasang.
const initialSession = loadStored();
setAuthToken(initialSession?.token || null);

export function AuthProvider({ children }) {
  const [session, setSession] = useState(initialSession);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      setAuthToken(null);
      localStorage.removeItem(STORAGE_KEY);
      setSession(null);
    });
    // Server bisa balas 403 MUST_CHANGE_PASSWORD kapan saja (bukan cuma
    // saat login) -- mis. admin reset password akun ini dari sesi lain
    // sementara akun ini masih terbuka di sini (lihat get_active_user di
    // backend). Tandai di session lokal supaya RequireAuth (App.jsx)
    // langsung mengarahkan ke /ganti-password di render berikutnya.
    setMustChangePasswordHandler(() => {
      setSession((prev) => {
        if (!prev || prev.mustChangePassword) return prev;
        const next = { ...prev, mustChangePassword: true };
        localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
        return next;
      });
    });
  }, []);

  const login = useCallback(async (username, password) => {
    const res = await api.login(username, password);
    // Role superadmin TIDAK punya tempat di dashboard ini -- akun itu murni
    // manajemen akun (lihat backend/auth/auth.py get_superadmin_user), dan
    // portalnya sengaja app terpisah (frontend-admin/), bukan halaman di
    // sini. Tolak di sini SEBELUM token dipasang/disimpan, supaya kredensial
    // yang valid tidak diam-diam membuka sesi (walau kosong datanya) di app
    // yang salah.
    if (res.role === "superadmin") {
      throw new Error("Akun ini adalah superadmin -- gunakan portal Manajemen Akun terpisah, bukan dashboard ini.");
    }
    const next = {
      token: res.access_token, role: res.role, scope: res.scope, username,
      mustChangePassword: !!res.must_change_password,
    };
    setAuthToken(next.token);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    setSession(next);
  }, []);

  const logout = useCallback(() => {
    setAuthToken(null);
    localStorage.removeItem(STORAGE_KEY);
    setSession(null);
  }, []);

  // Dipanggil setelah POST /auth/change-password sukses -- token lama tetap
  // valid (must_change_password dicek fresh dari DB tiap request di backend,
  // bukan dari isi token), jadi cukup perbarui flag lokal, tidak perlu token
  // baru atau login ulang.
  const markPasswordChanged = useCallback(() => {
    setSession((prev) => {
      if (!prev) return prev;
      const next = { ...prev, mustChangePassword: false };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      return next;
    });
  }, []);

  return (
    <AuthContext.Provider value={{ session, login, logout, markPasswordChanged }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
