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
      // Role admin/pmo TIDAK punya urusan di sini -- portal ini murni
      // manajemen akun, dashboard data koperasi ada di app terpisah
      // (frontend/). Ditolak di sini SEBELUM token disimpan, meski
      // kredensialnya sendiri valid.
      if (res.role !== "superadmin") {
        setError("Akun ini bukan superadmin -- gunakan dashboard utama, bukan portal Manajemen Akun ini.");
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
        <p className="page-desc">Portal Manajemen Akun -- khusus superadmin.</p>

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
          Tidak ada pendaftaran mandiri -- akun superadmin dibuat lewat{" "}
          <code>backend/auth/create_user.py --role superadmin</code>.
        </p>
      </form>
    </div>
  );
}
