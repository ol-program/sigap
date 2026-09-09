import { NavLink, Link } from "react-router-dom";
import { useAuth } from "../AuthContext.jsx";

function NavIcon({ path }) {
  return (
    <svg className="nav-icon" viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      {path}
    </svg>
  );
}

const ICONS = {
  ringkasan: <><rect x="3" y="13" width="4" height="8" /><rect x="10" y="8" width="4" height="13" /><rect x="17" y="4" width="4" height="17" /></>,
  koperasi: <><line x1="4" y1="6" x2="20" y2="6" /><line x1="4" y1="12" x2="20" y2="12" /><line x1="4" y1="18" x2="14" y2="18" /></>,
  notifikasi: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" /><path d="M13.73 21a2 2 0 0 1-3.46 0" /></>,
  metodologi: <><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" /><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" /></>,
  key: <><circle cx="8" cy="15" r="4" /><path d="M10.5 12.5 20 3" /><path d="M17 6l2 2" /><path d="M14 9l2 2" /></>,
  logout: <><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><polyline points="16 17 21 12 16 7" /><line x1="21" y1="12" x2="9" y2="12" /></>,
};

function NavItem({ to, end, icon, children }) {
  return (
    <NavLink to={to} end={end} className={({ isActive }) => (isActive ? "active" : "")}>
      <NavIcon path={ICONS[icon]} />
      {children}
    </NavLink>
  );
}

function initials(username) {
  return (username || "?").slice(0, 2).toUpperCase();
}

export default function Sidebar() {
  const { session, logout } = useAuth();

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <img src="/branding/sigap-mark.svg" alt="" width={28} height={28} />
        <h1>SIGAP Kopdes</h1>
      </div>
      <p className="subtitle">Deteksi dini kelayakan usaha KDMP</p>
      <nav>
        <NavItem to="/" end icon="ringkasan">Ringkasan</NavItem>
        <NavItem to="/koperasi" icon="koperasi">Daftar Koperasi</NavItem>
        <NavItem to="/notifikasi" icon="notifikasi">Notifikasi</NavItem>
        <NavItem to="/metodologi" icon="metodologi">Kriteria &amp; Metodologi</NavItem>
      </nav>

      <div className="sidebar-user">
        <div className="user-card">
          <div className="user-avatar">{initials(session.username)}</div>
          <div className="user-meta">
            <div className="user-name">{session.username}</div>
            <div className="user-role">
              {session.role === "admin" ? "Pemerintah Pusat (Admin)" : `PMO -- ${session.scope.length} wilayah`}
            </div>
          </div>
        </div>
        <Link to="/ganti-password" className="btn btn-sm sidebar-action">
          <NavIcon path={ICONS.key} />
          Ganti Password
        </Link>
        <button onClick={logout} className="btn-ghost-danger sidebar-action">
          <NavIcon path={ICONS.logout} />
          Keluar
        </button>
      </div>
    </aside>
  );
}
