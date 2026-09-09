import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import PetaWilayah from "../components/PetaWilayah.jsx";
import InfoTooltip from "../components/InfoTooltip.jsx";

export default function RingkasanPage() {
  const [ringkasan, setRingkasan] = useState(null);
  const [notifBelum, setNotifBelum] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    Promise.all([
      api.ringkasan(),
      api.notifikasi({ status_tindak_lanjut: "Baru" }),
    ])
      .then(([r, n]) => {
        setRingkasan(r);
        setNotifBelum(n.slice(0, 8));
      })
      .catch((e) => setError(e.message));
  }, []);

  if (error) return <div className="error-state">{error}</div>;
  if (!ringkasan) return <div className="loading-state">Memuat ringkasan...</div>;

  const per = ringkasan.per_kategori || {};

  return (
    <div>
      <h2>Ringkasan</h2>
      <p className="page-desc">
        Periode {ringkasan.periode} &middot; agregat dari skor kelayakan &amp; notifikasi terbaru. Arti tiap
        angka: lihat <Link to="/metodologi">Kriteria &amp; Metodologi</Link>.
      </p>

      <div className="stat-grid">
        <div className="stat-tile">
          <div className="label">
            Rata-rata skor komposit
            <InfoTooltip text="Rata-rata skor 0-100 seluruh koperasi (dalam scope Anda) pada periode ini. Skor dihitung dari 3 sub-skor: transaksi, stok, pelaporan." />
          </div>
          <div className="value">{ringkasan.rata_rata_skor_komposit ?? "-"}</div>
        </div>
        <div className="stat-tile">
          <div className="label"><span className="status-dot good" /> Sehat</div>
          <div className="value">{per.Sehat ?? 0}</div>
        </div>
        <div className="stat-tile">
          <div className="label"><span className="status-dot warning" /> Waspada</div>
          <div className="value">{per.Waspada ?? 0}</div>
        </div>
        <div className="stat-tile">
          <div className="label"><span className="status-dot critical" /> Kritis</div>
          <div className="value">{per.Kritis ?? 0}</div>
        </div>
        <div className="stat-tile">
          <div className="label">
            Notifikasi belum ditindaklanjuti
            <InfoTooltip text="Koperasi yang baru masuk kategori Kritis, atau skornya turun signifikan dari bulan sebelumnya." />
          </div>
          <div className="value">{ringkasan.notifikasi_belum_ditindaklanjuti ?? 0}</div>
        </div>
      </div>

      <PetaWilayah />

      <div className="card">
        <h4 style={{ marginTop: 0 }}>Notifikasi terbaru yang belum ditindaklanjuti</h4>
        {notifBelum.length === 0 ? (
          <p className="page-desc" style={{ margin: 0 }}>Tidak ada notifikasi tertunda.</p>
        ) : (
          <div className="table-wrap" style={{ border: "none" }}>
            <table>
              <thead>
                <tr>
                  <th>Tanggal</th>
                  <th>Koperasi</th>
                  <th>Jenis alert</th>
                </tr>
              </thead>
              <tbody>
                {notifBelum.map((n) => (
                  <tr key={n.notifikasi_id}>
                    <td>{n.tanggal}</td>
                    <td><Link to={`/koperasi/${n.koperasi_id}`}>{n.koperasi_id}</Link></td>
                    <td>{n.jenis_alert}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
