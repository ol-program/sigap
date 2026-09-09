import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";

export default function NotifikasiPage() {
  const [status, setStatus] = useState("");
  const [statusOptions, setStatusOptions] = useState([]);
  const [rows, setRows] = useState(null);
  const [error, setError] = useState(null);

  // status_tindak_lanjut belum punya enum resmi -- opsi filter diambil dari data yang ada.
  useEffect(() => {
    api.notifikasi().then((all) => {
      setStatusOptions([...new Set(all.map((n) => n.status_tindak_lanjut))]);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    setRows(null);
    api
      .notifikasi({ status_tindak_lanjut: status || undefined })
      .then(setRows)
      .catch((e) => setError(e.message));
  }, [status]);

  return (
    <div>
      <h2>Notifikasi</h2>
      <p className="page-desc">Notifikasi otomatis saat skor koperasi turun signifikan atau masuk kategori Kritis.</p>

      <div className="filters-row">
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">Semua status</option>
          {statusOptions.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>

      {error && <div className="error-state">{error}</div>}
      {!error && !rows && <div className="loading-state">Memuat notifikasi...</div>}
      {!error && rows && rows.length === 0 && <div className="empty-state">Tidak ada notifikasi.</div>}
      {!error && rows && rows.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Tanggal</th>
                <th>Koperasi</th>
                <th>Jenis alert</th>
                <th>Status tindak lanjut</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((n) => (
                <tr key={n.notifikasi_id}>
                  <td>{n.tanggal}</td>
                  <td><Link to={`/koperasi/${n.koperasi_id}`}>{n.koperasi_id}</Link></td>
                  <td>{n.jenis_alert}</td>
                  <td><span className="status-badge">{n.status_tindak_lanjut}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
