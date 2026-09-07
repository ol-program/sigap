import { useState } from "react";
import { api } from "../api.js";

export default function ChangePasswordPage({ onChanged, onLogout }) {
  const [passwordLama, setPasswordLama] = useState("");
  const [passwordBaru, setPasswordBaru] = useState("");
  const [passwordUlangi, setPasswordUlangi] = useState("");
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    if (passwordBaru !== passwordUlangi) {
      setError("Password baru dan ulangi password tidak cocok.");
      return;
    }
    setLoading(true);
    try {
      await api.changePassword(passwordLama, passwordBaru);
      onChanged();
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
      <form onSubmit={handleSubmit} className="card" style={{ width: 340 }}>
        <h2 style={{ marginTop: 0 }}>Ganti Password</h2>
        <p className="page-desc">
          Akun superadmin ini dibuat dengan password sementara -- ganti dulu sebelum melanjutkan.
        </p>

        <div className="form-field">
          <label>Password saat ini</label>
          <input type="password" value={passwordLama} onChange={(e) => setPasswordLama(e.target.value)} autoFocus required />
        </div>
        <div className="form-field">
          <label>Password baru</label>
          <input type="password" value={passwordBaru} onChange={(e) => setPasswordBaru(e.target.value)} minLength={8} required />
          <div className="field-hint">Minimal 8 karakter, harus berbeda dari password saat ini.</div>
        </div>
        <div className="form-field">
          <label>Ulangi password baru</label>
          <input type="password" value={passwordUlangi} onChange={(e) => setPasswordUlangi(e.target.value)} minLength={8} required />
        </div>

        {error && <div className="error-state" style={{ padding: "8px 0", textAlign: "left" }}>{error}</div>}

        <button type="submit" className="btn btn-primary" disabled={loading} style={{ width: "100%" }}>
          {loading ? "Memproses..." : "Ganti Password"}
        </button>

        <button
          type="button"
          onClick={onLogout}
          style={{
            marginTop: 16, background: "none", border: "none", color: "var(--text-muted)",
            fontSize: 12, cursor: "pointer", textDecoration: "underline", padding: 0,
          }}
        >
          Keluar
        </button>
      </form>
    </div>
  );
}
