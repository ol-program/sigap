import { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { api } from "../api.js";
import { useAuth } from "../AuthContext.jsx";

export default function ChangePasswordPage() {
  const { session, markPasswordChanged } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const forced = session?.mustChangePassword;

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
      markPasswordChanged();
      navigate(location.state?.from || "/", { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h2>Ganti Password</h2>
      <p className="page-desc">
        {forced
          ? "Akun Anda dibuat oleh admin dengan password sementara -- ganti dulu sebelum melanjutkan ke dashboard."
          : "Ganti password akun Anda."}
      </p>

      <form onSubmit={handleSubmit} className="card" style={{ maxWidth: 380 }}>
        <div className="form-field">
          <label>Password saat ini</label>
          <input
            type="password"
            value={passwordLama}
            onChange={(e) => setPasswordLama(e.target.value)}
            autoFocus
            required
          />
        </div>
        <div className="form-field">
          <label>Password baru</label>
          <input
            type="password"
            value={passwordBaru}
            onChange={(e) => setPasswordBaru(e.target.value)}
            minLength={8}
            required
          />
          <div className="field-hint">Minimal 8 karakter, harus berbeda dari password saat ini.</div>
        </div>
        <div className="form-field">
          <label>Ulangi password baru</label>
          <input
            type="password"
            value={passwordUlangi}
            onChange={(e) => setPasswordUlangi(e.target.value)}
            minLength={8}
            required
          />
        </div>

        {error && <div className="error-state" style={{ padding: "8px 0", textAlign: "left" }}>{error}</div>}

        <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
          <button type="submit" className="btn btn-primary" disabled={loading} style={{ flex: 1 }}>
            {loading ? "Memproses..." : "Ganti Password"}
          </button>
          {!forced && (
            <button type="button" className="btn" onClick={() => navigate(-1)}>
              Batal
            </button>
          )}
        </div>
      </form>
    </div>
  );
}
