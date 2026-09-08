import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { api, setAuthToken, setUnauthorizedHandler, setMustChangePasswordHandler } from "./api.js";

const STORAGE_KEY = "sigap_auth";
const AuthContext = createContext(null);

// Token JWT di localStorage -- rentan XSS dibanding httpOnly cookie; cukup
// untuk tool internal ini, tapi pindahkan kalau nanti ada script pihak ketiga.
function loadStored() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

// authToken di-set sinkron di sini (bukan lewat useEffect) supaya tidak ada
// request yang berangkat tanpa token sebelum child pertama mount.
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
    // Server bisa balas 403 MUST_CHANGE_PASSWORD kapan saja (mis. admin
    // reset password akun ini dari sesi lain) -- tandai di session lokal
    // supaya RequireAuth (App.jsx) mengarahkan ke /ganti-password.
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
    // Role superadmin punya portal terpisah (frontend-admin/) -- tolak di
    // sini sebelum token dipasang, supaya kredensial valid tidak membuka
    // sesi di app yang salah.
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

  // Token lama tetap valid setelah ganti password (backend cek fresh dari
  // DB, bukan dari isi token) -- cukup perbarui flag lokal.
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
