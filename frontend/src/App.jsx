import { Routes, Route, Navigate, useLocation } from "react-router-dom";
import RingkasanPage from "./pages/RingkasanPage.jsx";
import KoperasiListPage from "./pages/KoperasiListPage.jsx";
import KoperasiDetailPage from "./pages/KoperasiDetailPage.jsx";
import NotifikasiPage from "./pages/NotifikasiPage.jsx";
import MetodologiPage from "./pages/MetodologiPage.jsx";
import LoginPage from "./pages/LoginPage.jsx";
import ChangePasswordPage from "./pages/ChangePasswordPage.jsx";
import Sidebar from "./components/Sidebar.jsx";
import { useAuth } from "./AuthContext.jsx";

// mustChangePassword tetap dibolehkan lewat -- kalau tidak, /ganti-password
// sendiri (yang dirender di dalam Shell) akan me-redirect ke dirinya sendiri
// tanpa henti.
function RequireAuth({ children }) {
  const { session } = useAuth();
  const location = useLocation();
  if (!session) return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  if (session.mustChangePassword && location.pathname !== "/ganti-password") {
    return <Navigate to="/ganti-password" state={{ from: location.pathname }} replace />;
  }
  return children;
}

function Shell() {
  return (
    <div className="app-shell">
      <Sidebar />
      <main className="main-content">
        <Routes>
          <Route path="/" element={<RingkasanPage />} />
          <Route path="/koperasi" element={<KoperasiListPage />} />
          <Route path="/koperasi/:koperasiId" element={<KoperasiDetailPage />} />
          <Route path="/notifikasi" element={<NotifikasiPage />} />
          <Route path="/metodologi" element={<MetodologiPage />} />
          <Route path="/ganti-password" element={<ChangePasswordPage />} />
        </Routes>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/*" element={<RequireAuth><Shell /></RequireAuth>} />
    </Routes>
  );
}
