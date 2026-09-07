import { useEffect, useState } from "react";
import { api } from "../api.js";
import AiKeyCard from "../components/AiKeyCard.jsx";

function UserFormModal({ mode, initialUser, kabupatenOptions, onClose, onSaved }) {
  const isEdit = mode === "edit";
  const [username, setUsername] = useState(initialUser?.username || "");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState(initialUser?.role || "pmo");
  const [kabupaten, setKabupaten] = useState(new Set(initialUser?.kabupaten_list || []));
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const toggleKabupaten = (nama) => {
    setKabupaten((prev) => {
      const next = new Set(prev);
      if (next.has(nama)) next.delete(nama);
      else next.add(nama);
      return next;
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    if (role === "pmo" && kabupaten.size === 0) {
      setError("Pilih minimal satu kabupaten/kota untuk role pmo (scope kosong berarti tidak bisa lihat data apa pun).");
      return;
    }
    setLoading(true);
    try {
      if (isEdit) {
        await api.adminUpdateUser(initialUser.username, { role, kabupaten_list: [...kabupaten] });
      } else {
        await api.adminCreateUser({ username: username.trim(), password, role, kabupaten_list: [...kabupaten] });
      }
      onSaved();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <form className="card modal-card" onClick={(e) => e.stopPropagation()} onSubmit={handleSubmit}>
        <h3>{isEdit ? `Edit Akun -- ${initialUser.username}` : "Tambah Akun"}</h3>

        {!isEdit && (
          <div className="form-field">
            <label>Username</label>
            <input value={username} onChange={(e) => setUsername(e.target.value)} autoFocus required />
          </div>
        )}
        {!isEdit && (
          <div className="form-field">
            <label>Password awal</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              minLength={8}
              required
            />
            <div className="field-hint">
              Minimal 8 karakter. Pemilik akun akan DIWAJIBKAN menggantinya saat login pertama.
            </div>
          </div>
        )}

        <div className="form-field">
          <label>Role</label>
          <select value={role} onChange={(e) => setRole(e.target.value)}>
            <option value="pmo">PMO -- akses terbatas wilayah tertentu</option>
            <option value="admin">Pemerintah Pusat (Admin) -- akses semua wilayah (data koperasi)</option>
          </select>
          <div className="field-hint">
            Superadmin tidak ada di pilihan ini -- sistem cuma boleh punya satu, dibuat sekali lewat CLI saat
            bootstrap (lihat README).
          </div>
        </div>

        {role === "pmo" && (
          <div className="form-field">
            <label>Wilayah (kabupaten/kota) yang boleh diakses</label>
            <div className="checkbox-grid">
              {kabupatenOptions.map((nama) => (
                <label key={nama}>
                  <input
                    type="checkbox"
                    checked={kabupaten.has(nama)}
                    onChange={() => toggleKabupaten(nama)}
                  />
                  {nama}
                </label>
              ))}
            </div>
            <div className="field-hint">{kabupaten.size} kabupaten/kota dipilih.</div>
          </div>
        )}

        {error && <div className="error-state" style={{ padding: "8px 0", textAlign: "left" }}>{error}</div>}

        <div className="row-actions" style={{ marginTop: 4 }}>
          <button type="submit" className="btn btn-primary" disabled={loading}>
            {loading ? "Menyimpan..." : "Simpan"}
          </button>
          <button type="button" className="btn" onClick={onClose} disabled={loading}>
            Batal
          </button>
        </div>
      </form>
    </div>
  );
}

function ResetPasswordModal({ user, onClose, onSaved }) {
  const [passwordBaru, setPasswordBaru] = useState("");
  const [passwordUlangi, setPasswordUlangi] = useState("");
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    if (passwordBaru !== passwordUlangi) {
      setError("Password dan ulangi password tidak cocok.");
      return;
    }
    setLoading(true);
    try {
      await api.adminResetPassword(user.username, passwordBaru);
      onSaved();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <form className="card modal-card" onClick={(e) => e.stopPropagation()} onSubmit={handleSubmit}>
        <h3>Reset Password -- {user.username}</h3>
        <p className="page-desc">
          Akun ini akan DIWAJIBKAN mengganti password ini lagi saat login berikutnya.
        </p>

        <div className="form-field">
          <label>Password baru</label>
          <input type="password" value={passwordBaru} onChange={(e) => setPasswordBaru(e.target.value)} minLength={8} autoFocus required />
        </div>
        <div className="form-field">
          <label>Ulangi password baru</label>
          <input type="password" value={passwordUlangi} onChange={(e) => setPasswordUlangi(e.target.value)} minLength={8} required />
        </div>

        {error && <div className="error-state" style={{ padding: "8px 0", textAlign: "left" }}>{error}</div>}

        <div className="row-actions" style={{ marginTop: 4 }}>
          <button type="submit" className="btn btn-primary" disabled={loading}>
            {loading ? "Menyimpan..." : "Reset Password"}
          </button>
          <button type="button" className="btn" onClick={onClose} disabled={loading}>
            Batal
          </button>
        </div>
      </form>
    </div>
  );
}

function roleLabel(role) {
  if (role === "admin") return "Pemerintah Pusat (Admin)";
  if (role === "superadmin") return "Superadmin";
  return "PMO";
}

export default function UsersPage({ session, onLogout }) {
  const [users, setUsers] = useState(null);
  const [kabupatenOptions, setKabupatenOptions] = useState([]);
  const [error, setError] = useState(null);
  const [modal, setModal] = useState(null); // {type:'create'} | {type:'edit', user} | {type:'reset', user}
  const [confirmDelete, setConfirmDelete] = useState(null); // username
  const [deleteError, setDeleteError] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const load = () => {
    setError(null);
    api.adminListUsers().then(setUsers).catch((e) => setError(e.message));
  };

  useEffect(() => {
    load();
    api.adminListKabupaten().then(setKabupatenOptions).catch(() => {});
  }, []);

  const closeModal = () => setModal(null);
  const handleSaved = () => {
    setModal(null);
    load();
  };

  const handleDelete = async (username) => {
    setDeleteError(null);
    setDeleting(true);
    try {
      await api.adminDeleteUser(username);
      setConfirmDelete(null);
      load();
    } catch (err) {
      setDeleteError(err.message);
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div style={{ maxWidth: 1100, margin: "0 auto", padding: "32px 24px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 4 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <img src="/branding/sigap-mark.svg" alt="" width={24} height={24} style={{ flexShrink: 0 }} />
            <h2 style={{ margin: 0 }}>Manajemen Akun</h2>
          </div>
          <p className="page-desc">
            Portal superadmin SIGAP Kopdes -- kelola akun login dashboard (admin &amp; PMO). Akun baru dan reset
            password mewajibkan pemiliknya mengganti password saat login berikutnya.
          </p>
        </div>
        <div style={{ textAlign: "right", flexShrink: 0, marginLeft: 16 }}>
          <div style={{ fontSize: 13, fontWeight: 600 }}>{session.username}</div>
          <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 8 }}>Superadmin</div>
          <button className="btn btn-sm" onClick={onLogout}>Keluar</button>
        </div>
      </div>

      <div className="filters-row">
        <button className="btn btn-primary" onClick={() => setModal({ type: "create" })}>
          + Tambah Akun
        </button>
      </div>

      {error && <div className="error-state">{error}</div>}
      {!error && !users && <div className="loading-state">Memuat daftar akun...</div>}
      {!error && users && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Username</th>
                <th>Role</th>
                <th>Wilayah</th>
                <th>Status password</th>
                <th>Aksi</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.username}>
                  <td>
                    {u.username}
                    {u.username === session.username && (
                      <span style={{ color: "var(--text-muted)", fontSize: 12 }}> (Anda)</span>
                    )}
                  </td>
                  <td>{roleLabel(u.role)}</td>
                  <td>
                    {u.role === "admin"
                      ? "Semua wilayah"
                      : u.role === "superadmin"
                        ? "-- (manajemen akun, bukan data)"
                        : u.kabupaten_list.length > 0
                          ? u.kabupaten_list.join(", ")
                          : "-- (tidak ada scope, fail closed)"}
                  </td>
                  <td>
                    {u.must_change_password
                      ? <span className="badge-warn">Perlu ganti password</span>
                      : <span className="badge-ok">Aktif</span>}
                  </td>
                  <td>
                    {u.role === "superadmin" ? (
                      <span style={{ fontSize: 12, color: "var(--text-muted)" }}>
                        -- (kelola lewat CLI, bukan portal ini)
                      </span>
                    ) : confirmDelete === u.username ? (
                      <div className="row-actions">
                        <span style={{ fontSize: 12, color: "var(--status-critical)" }}>Yakin hapus?</span>
                        <button className="btn btn-danger btn-sm" disabled={deleting} onClick={() => handleDelete(u.username)}>
                          Ya, hapus
                        </button>
                        <button className="btn btn-sm" disabled={deleting} onClick={() => { setConfirmDelete(null); setDeleteError(null); }}>
                          Batal
                        </button>
                      </div>
                    ) : (
                      <div className="row-actions">
                        <button className="btn btn-sm" onClick={() => setModal({ type: "edit", user: u })}>Edit</button>
                        <button className="btn btn-sm" onClick={() => setModal({ type: "reset", user: u })}>Reset Password</button>
                        <button
                          className="btn btn-danger btn-sm"
                          disabled={u.username === session.username}
                          title={u.username === session.username ? "Tidak bisa menghapus akun sendiri" : undefined}
                          onClick={() => { setConfirmDelete(u.username); setDeleteError(null); }}
                        >
                          Hapus
                        </button>
                      </div>
                    )}
                    {confirmDelete === u.username && deleteError && (
                      <div className="error-state" style={{ padding: "4px 0", textAlign: "left" }}>{deleteError}</div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div style={{ marginTop: 32 }}>
        <AiKeyCard />
      </div>

      {modal?.type === "create" && (
        <UserFormModal mode="create" kabupatenOptions={kabupatenOptions} onClose={closeModal} onSaved={handleSaved} />
      )}
      {modal?.type === "edit" && (
        <UserFormModal mode="edit" initialUser={modal.user} kabupatenOptions={kabupatenOptions} onClose={closeModal} onSaved={handleSaved} />
      )}
      {modal?.type === "reset" && (
        <ResetPasswordModal user={modal.user} onClose={closeModal} onSaved={handleSaved} />
      )}
    </div>
  );
}
