import { useEffect, useState } from "react";
import { api } from "../api.js";

function toList(val) {
  return Array.isArray(val) ? val : [val];
}

// AI Insight dibuat ON-DEMAND, bukan di-batch untuk semua koperasi di muka:
// kalau `initial` (dari respons /koperasi/{id}) kosong, komponen ini memanggil
// GET /insight/{id} sendiri -- backend akan generate saat itu juga (realtime,
// ~2-15 detik tergantung provider) kalau belum pernah dibuat, lalu menyimpannya
// supaya kunjungan berikutnya ke koperasi yang sama langsung dari cache.
export default function AiInsightCard({ koperasiId, initial }) {
  const [insight, setInsight] = useState(initial || null);
  const [loading, setLoading] = useState(!initial);
  const [error, setError] = useState(null);
  // Animasi "muncul" cuma untuk hasil yang BARU selesai di-generate di sesi
  // ini -- kalau sudah dari cache (initial), tampil langsung tanpa animasi
  // supaya tidak berkedip tiap kali halaman dibuka ulang.
  const [justGenerated, setJustGenerated] = useState(false);

  useEffect(() => {
    setInsight(initial || null);
    setError(null);
    setJustGenerated(false);
    if (initial) {
      setLoading(false);
      return;
    }
    setLoading(true);
    api.insight(koperasiId)
      .then((data) => {
        setInsight(data);
        setJustGenerated(true);
      })
      .catch((e) => setError(e))
      .finally(() => setLoading(false));
  }, [koperasiId, initial]);

  if (loading) {
    return (
      <div className="insight-loading">
        <div className="thinking-label">
          Membuat AI insight untuk koperasi ini
          <span className="thinking-dots"><span /><span /><span /></span>
        </div>
        <div className="skeleton-block" style={{ width: "88%" }} />
        <div className="skeleton-block" style={{ width: "72%" }} />
        <div className="skeleton-block" style={{ width: "60%", marginBottom: 18 }} />
        <div className="skeleton-block" style={{ width: "82%" }} />
        <div className="skeleton-block" style={{ width: "68%" }} />
      </div>
    );
  }

  if (error) {
    // error.message sudah kalimat lengkap siap-tampil dari backend (lihat
    // ringkas_error_llm() di api/main.py) -- jangan ditambah prefix lagi di
    // sini, dulu sempat dobel jadi "Gagal membuat AI insight: Gagal..." saat
    // kuota Gemini gratis benar-benar habis di pengujian.
    const belumDikonfigurasi = error.status === 503;
    return (
      <p className="page-desc" style={{ margin: 0 }}>
        {belumDikonfigurasi
          ? "AI insight belum bisa dibuat otomatis -- server belum dikonfigurasi API key provider LLM (ANTHROPIC_API_KEY atau GEMINI_API_KEY)."
          : error.message}
      </p>
    );
  }

  if (!insight) {
    return <p className="page-desc" style={{ margin: 0 }}>Belum ada AI insight untuk koperasi ini.</p>;
  }

  // Satu section terstruktur (bukan 5 kotak bersarang terpisah) -- narasi
  // jadi pengantar tanpa kotak, lalu dua rekomendasi singkat berdampingan,
  // lalu dua daftar (produk & program) berdampingan. Reveal animation tetap
  // stagger per bagian saat baru selesai di-generate (bukan dari cache).
  const revealStyle = (i) => (justGenerated ? { animationDelay: `${i * 80}ms` } : undefined);
  const revealCls = justGenerated ? " insight-reveal" : "";

  return (
    <div className="insight-body">
      <p className={`insight-narasi${revealCls}`} style={revealStyle(0)}>{insight.narasi}</p>

      <div className="insight-divider" />

      <div className={`insight-grid${revealCls}`} style={revealStyle(1)}>
        <div className="insight-section">
          <h5>Rekomendasi Tindakan</h5>
          <p>{insight.rekomendasi_tindakan}</p>
        </div>
        <div className="insight-section">
          <h5>Rekomendasi Promosi</h5>
          <p>{insight.rekomendasi_promosi}</p>
        </div>
      </div>

      <div className="insight-divider" />

      <div className={`insight-grid${revealCls}`} style={revealStyle(2)}>
        <div className="insight-section">
          <h5>Produk &amp; Jasa Prioritas</h5>
          <ul>
            {toList(insight.produk_prioritas).map((item, i) => <li key={i}>{item}</li>)}
          </ul>
        </div>
        <div className="insight-section">
          <h5>Program Pengembangan</h5>
          <ul>
            {toList(insight.rekomendasi_program).map((item, i) => <li key={i}>{item}</li>)}
          </ul>
        </div>
      </div>
    </div>
  );
}
