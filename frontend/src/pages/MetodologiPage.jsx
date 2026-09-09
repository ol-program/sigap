import { useEffect, useState } from "react";
import { api } from "../api.js";

// Angka ambang/bobot diambil dari /metodologi, bukan di-hardcode, supaya
// tidak menyimpang dari compute_scores.py & predict_risk.py.
export default function MetodologiPage() {
  const [m, setM] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.metodologi().then(setM).catch((e) => setError(e.message));
  }, []);

  if (error) return <div className="error-state">{error}</div>;
  if (!m) return <div className="loading-state">Memuat...</div>;

  const bobotPct = (v) => Math.round(v * 100);

  return (
    <div>
      <h2>Kriteria &amp; Metodologi</h2>
      <p className="page-desc">
        Penjelasan lengkap arti tiap angka &amp; kategori di dashboard ini, supaya tidak perlu menebak-nebak.
      </p>

      <div className="metodologi-section card">
        <h3>Kategori kelayakan koperasi</h3>
        <p className="page-desc">Ditentukan dari skor komposit (0-100) koperasi pada periode berjalan:</p>
        <div className="kriteria-legend">
          <div><span className="status-dot good" /> <strong>Sehat</strong> — skor ≥ {m.batas_sehat}</div>
          <div><span className="status-dot warning" /> <strong>Waspada</strong> — skor {m.batas_waspada}–{m.batas_sehat - 1}</div>
          <div><span className="status-dot critical" /> <strong>Kritis</strong> — skor &lt; {m.batas_waspada}</div>
        </div>
        <p className="page-desc" style={{ margin: 0 }}>
          Kategori yang sama dipakai untuk kartu Ringkasan, Daftar Koperasi, Detail Koperasi, dan warna agregat di Peta —
          untuk peta, kategori dihitung dari <em>rata-rata</em> skor koperasi di wilayah itu, jadi tidak berarti semua
          koperasi di sana berkategori sama persis.
        </p>
      </div>

      <div className="metodologi-section card">
        <h3>Skor komposit</h3>
        <p className="page-desc">
          Rata-rata tertimbang dari 3 sub-skor, masing-masing 0-100:
        </p>
        <div className="table-wrap" style={{ border: "none", marginBottom: 12 }}>
          <table className="kriteria-table">
            <thead>
              <tr><th>Sub-skor</th><th>Bobot</th><th>Cara hitung</th></tr>
            </thead>
            <tbody>
              <tr>
                <td>Transaksi</td>
                <td>{bobotPct(m.bobot_skor_komposit.transaksi)}%</td>
                <td>Peringkat persentil jumlah &amp; total nilai transaksi bulan itu, <strong>relatif terhadap semua koperasi lain</strong> pada periode yang sama (bukan nilai rupiah absolut).</td>
              </tr>
              <tr>
                <td>Stok</td>
                <td>{bobotPct(m.bobot_skor_komposit.stok)}%</td>
                <td>Peringkat persentil jumlah unit stok, relatif terhadap populasi koperasi yang sama.</td>
              </tr>
              <tr>
                <td>Pelaporan</td>
                <td>{bobotPct(m.bobot_skor_komposit.pelaporan)}%</td>
                <td>Persen kelengkapan laporan bulan itu — skala absolut (100% = laporan lengkap), bukan persentil.</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p className="page-desc" style={{ margin: 0 }}>
          <strong>Kenapa persentil, bukan nilai mentah?</strong> Nilai transaksi biasanya timpang (banyak koperasi kecil,
          sedikit yang sangat besar) — pakai peringkat relatif menghindari mayoritas koperasi selalu terlihat rendah
          meski posisinya biasa saja. Konsekuensinya: skor Transaksi &amp; Stok bersifat <strong>relatif terhadap
          koperasi yang sedang dipantau saat ini</strong>, bukan skala absolut universal.
        </p>
      </div>

      <div className="metodologi-section card">
        <h3>Proyeksi risiko Kritis {m.gap_bulan_prediksi} bulan</h3>
        <p className="page-desc" style={{ margin: 0 }}>
          Persentase kemungkinan sebuah koperasi akan berkategori <strong>Kritis</strong> {m.gap_bulan_prediksi} bulan dari
          sekarang, dari model prediktif yang dilatih dari histori skor &amp; tren (bukan cuma snapshot skor saat ini).
          Model ini dilatih dari data simulasi dalam jumlah terbatas — angkanya <strong>indikatif untuk prototipe</strong>,
          bukan klaim yang sudah divalidasi untuk produksi.
        </p>
      </div>

      <div className="metodologi-section card">
        <h3>Notifikasi otomatis</h3>
        <p className="page-desc" style={{ margin: 0 }}>
          Diterbitkan otomatis kalau (a) skor komposit koperasi masuk kategori <strong>Kritis</strong>, atau
          (b) skor komposit turun ≥ <strong>{m.turun_signifikan} poin</strong> dari bulan sebelumnya. Status "Baru" berarti
          belum ada tindak lanjut yang tercatat.
        </p>
      </div>

      <div className="metodologi-section card">
        <h3>Status kemajuan desa (IDM)</h3>
        <p className="page-desc">
          <strong>Berbeda dari kategori kelayakan koperasi di atas.</strong> Ini indeks resmi Kemendes PDTT (Indeks Desa
          Membangun) yang menggambarkan kondisi WILAYAH desa/kelurahannya — dimensi sosial, ekonomi, dan lingkungan —
          bukan kondisi operasional koperasinya sendiri. Dipakai sebagai konteks untuk rekomendasi produk/promosi AI
          Insight, bukan komponen penghitung skor komposit koperasi.
        </p>
        <div className="kriteria-legend" style={{ marginBottom: 0 }}>
          {["Mandiri", "Maju", "Berkembang", "Tertinggal", "Sangat Tertinggal"].map((s) => (
            <div key={s}>{s}</div>
          ))}
        </div>
      </div>
    </div>
  );
}
