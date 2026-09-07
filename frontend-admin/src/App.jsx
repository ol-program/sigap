import { useEffect, useState, useCallback } from "react";
import { setAuthToken, setUnauthorizedHandler } from "./api.js";
import LoginPage from "./pages/LoginPage.jsx";
import ChangePasswordPage from "./pages/ChangePasswordPage.jsx";
import UsersPage from "./pages/UsersPage.jsx";

// Key BEDA dari frontend/ ("sigap_auth") SENGAJA -- walau dua app ini juga
// sudah terisolasi lewat origin/localStorage berbeda (subdomain berbeda),
// nama key yang beda bikin jelas kalau dua devtools/localStorage dibuka
// berdampingan yang mana punya siapa.
const STORAGE_KEY = "sigap_superadmin_auth";

function loadStored() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

const initialSession = loadStored();
setAuthToken(initialSession?.token || null);

export default function App() {
  const [session, setSession] = useState(initialSession);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      setAuthToken(null);
      localStorage.removeItem(STORAGE_KEY);
      setSession(null);
    });
  }, []);

  const handleLoggedIn = useCallback((res, username) => {
    const next = {
      token: res.access_token, username, mustChangePassword: !!res.must_change_password,
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

  const markPasswordChanged = useCallback(() => {
    setSession((prev) => {
      if (!prev) return prev;
      const next = { ...prev, mustChangePassword: false };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      return next;
    });
  }, []);

  if (!session) return <LoginPage onLoggedIn={handleLoggedIn} />;
  if (session.mustChangePassword) {
    return <ChangePasswordPage forced onChanged={markPasswordChanged} onLogout={logout} />;
  }
  return <UsersPage session={session} onLogout={logout} />;
}
