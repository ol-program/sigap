import { NavLink, Link, Routes, Route, Navigate, useLocation } from "react-router-dom";
import RingkasanPage from "./pages/RingkasanPage.jsx";
import KoperasiListPage from "./pages/KoperasiListPage.jsx";
import KoperasiDetailPage from "./pages/KoperasiDetailPage.jsx";
import NotifikasiPage from "./pages/NotifikasiPage.jsx";
import MetodologiPage from "./pages/MetodologiPage.jsx";
import LoginPage from "./pages/LoginPage.jsx";
import ChangePasswordPage from "./pages/ChangePasswordPage.jsx";
import { useAuth } from "./AuthContext.jsx";

function NavItem({ to, children, end }) {
  return (
    <NavLink to={to} end={end} className={({ isActive }) => (isActive ? "active" : "")}>
      {children}
    </NavLink>
  );
}

// Butuh login, TAPI TIDAK menolak mustChangePassword -- dipakai khusus untuk
// /ganti-password sendiri (kalau ikut menolak, user yang wajib ganti
// password tidak akan pernah bisa mencapai halaman untuk menggantinya).
function RequireLoggedIn({ children }) {
  const { session } = useAuth();
  const location = useLocation();
  if (!session) return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  return children;
}

function RequireAuth({ children }) {
  const { session } = useAuth();
  const location = useLocation();
  if (!session) return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  if (session.mustChangePassword) {
    return <Navigate to="/ganti-password" state={{ from: location.pathname }} replace />;
  }
  return children;
}

function Shell() {
  const { session, logout } = useAuth();
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
          <img src="/branding/sigap-mark.svg" alt="" width={28} height={28} style={{ flexShrink: 0 }} />
          <h1 style={{ margin: 0 }}>SIGAP Kopdes</h1>
        </div>
        <p className="subtitle">Deteksi dini kesehatan usaha KDMP</p>
        <nav>
          <NavItem to="/" end>Ringkasan</NavItem>
          <NavItem to="/koperasi">Daftar Koperasi</NavItem>
          <NavItem to="/notifikasi">Notifikasi</NavItem>
          <NavItem to="/metodologi">Kriteria &amp; Metodologi</NavItem>
        </nav>

        <div style={{ marginTop: 24, paddingTop: 16, borderTop: "1px solid var(--border)" }}>
          <div style={{ fontSize: 13, fontWeight: 600 }}>{session.username}</div>
          <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 8 }}>
            {session.role === "admin" ? "Pemerintah Pusat (Admin) -- semua wilayah" : `PMO -- ${session.scope.length} wilayah`}
          </div>
          <Link
            to="/ganti-password"
            className="btn btn-sm"
            style={{ display: "block", textAlign: "center", textDecoration: "none" }}
          >
            Ganti Password
          </Link>
          <button
            onClick={logout}
            className="btn btn-sm"
            style={{ marginTop: 8, width: "100%" }}
          >
            Keluar
          </button>
        </div>
      </aside>
      <main className="main-content">
        <Routes>
          <Route path="/" element={<RingkasanPage />} />
          <Route path="/koperasi" element={<KoperasiListPage />} />
          <Route path="/koperasi/:koperasiId" element={<KoperasiDetailPage />} />
          <Route path="/notifikasi" element={<NotifikasiPage />} />
          <Route path="/metodologi" element={<MetodologiPage />} />
        </Routes>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/ganti-password" element={<RequireLoggedIn><ChangePasswordPage /></RequireLoggedIn>} />
      <Route path="/*" element={<RequireAuth><Shell /></RequireAuth>} />
    </Routes>
  );
}
