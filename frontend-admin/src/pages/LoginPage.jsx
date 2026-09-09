import { useState } from "react";
import { api } from "../api.js";

export default function LoginPage({ onLoggedIn }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await api.login(username, password);
      // Portal ini murni manajemen akun -- role admin/pmo pakai dashboard di frontend/.
      if (res.role !== "superadmin") {
        setError("Akun ini bukan superadmin. Silakan gunakan dashboard utama, bukan portal Manajemen Akun ini.");
        return;
      }
      onLoggedIn(res, username);
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
        <p className="page-desc">Portal Manajemen Akun, khusus untuk superadmin.</p>

        <div className="form-field">
          <label>Username</label>
          <input value={username} onChange={(e) => setUsername(e.target.value)} autoFocus required />
        </div>
        <div className="form-field">
          <label>Password</label>
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </div>

        {error && <div className="error-state" style={{ padding: "8px 0", textAlign: "left" }}>{error}</div>}

        <button type="submit" className="btn btn-primary" disabled={loading} style={{ width: "100%" }}>
          {loading ? "Memproses..." : "Masuk"}
        </button>

        <p className="page-desc" style={{ marginTop: 16, marginBottom: 0, fontSize: 12 }}>
          Tidak ada pendaftaran mandiri. Akun superadmin dibuat melalui proses instalasi awal server.
        </p>
      </form>
    </div>
  );
}
