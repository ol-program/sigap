import { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../AuthContext.jsx";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(username, password);
      navigate(location.state?.from || "/", { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center",
      background: "var(--page-plane)",
    }}>
      <form onSubmit={handleSubmit} className="card" style={{ width: 320 }}>
        <img src="/branding/sigap-lockup.svg" alt="SIGAP Kopdes" height={40} className="logo-lockup-light" style={{ marginBottom: 16 }} />
        <img src="/branding/sigap-lockup-latar-gelap.svg" alt="SIGAP Kopdes" height={40} className="logo-lockup-dark" style={{ marginBottom: 16 }} />
        <p className="page-desc">Masuk untuk melihat dashboard.</p>

        <div style={{ marginBottom: 12 }}>
          <label style={{ display: "block", fontSize: 12, color: "var(--text-secondary)", marginBottom: 4 }}>Username</label>
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            style={{ width: "100%", padding: "8px 10px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--surface-1)", color: "var(--text-primary)" }}
            autoFocus
            required
          />
        </div>
        <div style={{ marginBottom: 16 }}>
          <label style={{ display: "block", fontSize: 12, color: "var(--text-secondary)", marginBottom: 4 }}>Password</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            style={{ width: "100%", padding: "8px 10px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--surface-1)", color: "var(--text-primary)" }}
            required
          />
        </div>

        {error && <div className="error-state" style={{ padding: "8px 0", textAlign: "left" }}>{error}</div>}

        <button
          type="submit"
          disabled={loading}
          style={{
            width: "100%", padding: "10px", borderRadius: 6, border: "none",
            background: "var(--series-1)", color: "#fff", fontWeight: 600, cursor: "pointer",
          }}
        >
          {loading ? "Memproses..." : "Masuk"}
        </button>

        <p className="page-desc" style={{ marginTop: 16, marginBottom: 0, fontSize: 12 }}>
          Tidak ada pendaftaran mandiri -- hubungi admin untuk membuat akun.
        </p>
      </form>
    </div>
  );
}
