import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import StatusBadge from "../components/StatusBadge.jsx";
import InfoTooltip from "../components/InfoTooltip.jsx";

export default function KoperasiListPage() {
  const [rows, setRows] = useState(null);
  const [wilayahList, setWilayahList] = useState([]);
  const [kategori, setKategori] = useState("");
  const [kodeWilayah, setKodeWilayah] = useState("");
  const [error, setError] = useState(null);

  useEffect(() => {
    api.wilayah().then(setWilayahList).catch(() => {});
  }, []);

  useEffect(() => {
    setRows(null);
    api
      .koperasiList({ kategori: kategori || undefined, kode_wilayah: kodeWilayah || undefined })
      .then(setRows)
      .catch((e) => setError(e.message));
  }, [kategori, kodeWilayah]);

  return (
    <div>
      <h2>Daftar Koperasi</h2>
      <p className="page-desc">
        Skor &amp; prediksi risiko periode terbaru per koperasi KDMP. Arti tiap kolom: lihat{" "}
        <Link to="/metodologi">Kriteria &amp; Metodologi</Link>.
      </p>

      <div className="filters-row">
        <select value={kategori} onChange={(e) => setKategori(e.target.value)}>
          <option value="">Semua kategori</option>
          <option value="Sehat">Sehat</option>
          <option value="Waspada">Waspada</option>
          <option value="Kritis">Kritis</option>
        </select>
        <select value={kodeWilayah} onChange={(e) => setKodeWilayah(e.target.value)}>
          <option value="">Semua wilayah</option>
          {wilayahList.map((w) => (
            <option key={w.kode_wilayah} value={w.kode_wilayah}>
              {w.desa_kelurahan}, {w.kabupaten_kota}
            </option>
          ))}
        </select>
      </div>

      {error && <div className="error-state">{error}</div>}
      {!error && !rows && <div className="loading-state">Memuat daftar koperasi...</div>}
      {!error && rows && rows.length === 0 && (
        <div className="empty-state">Tidak ada koperasi yang cocok dengan filter ini.</div>
      )}
      {!error && rows && rows.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Koperasi</th>
                <th>Wilayah</th>
                <th>Jenis usaha</th>
                <th>
                  Skor komposit
                  <InfoTooltip text="Rata-rata tertimbang 3 sub-skor (transaksi, stok, pelaporan), skala 0-100. Lihat halaman Kriteria & Metodologi untuk rincian." />
                </th>
                <th>
                  Kategori
                  <InfoTooltip text="Sehat / Waspada / Kritis, ditentukan dari ambang skor komposit. Lihat halaman Kriteria & Metodologi untuk angka pastinya." />
                </th>
                <th>
                  Risiko kritis 3bln
                  <InfoTooltip text="Proyeksi model prediktif: peluang koperasi ini berkategori Kritis 3 bulan dari sekarang. Indikatif (data simulasi), bukan validasi produksi." />
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.koperasi_id}>
                  <td><Link to={`/koperasi/${r.koperasi_id}`}>{r.nama_koperasi}</Link></td>
                  <td>{r.desa_kelurahan}, {r.kabupaten_kota}</td>
                  <td>{r.jenis_usaha}</td>
                  <td>{r.skor_komposit ?? "-"}</td>
                  <td><StatusBadge kategori={r.kategori} /></td>
                  <td>{r.prediksi_risiko_3bln != null ? `${r.prediksi_risiko_3bln}%` : "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
