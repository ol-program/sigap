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

  const blocks = [
    { title: "Narasi kondisi", body: <p style={{ margin: 0 }}>{insight.narasi}</p> },
    { title: "Rekomendasi tindakan", body: <p style={{ margin: 0 }}>{insight.rekomendasi_tindakan}</p> },
    {
      title: "Produk & jasa prioritas",
      body: (
        <ul style={{ margin: 0, paddingLeft: 18 }}>
          {toList(insight.produk_prioritas).map((item, i) => <li key={i}>{item}</li>)}
        </ul>
      ),
    },
    { title: "Rekomendasi promosi", body: <p style={{ margin: 0 }}>{insight.rekomendasi_promosi}</p> },
    {
      title: "Program pengembangan",
      body: (
        <ul style={{ margin: 0, paddingLeft: 18 }}>
          {toList(insight.rekomendasi_program).map((item, i) => <li key={i}>{item}</li>)}
        </ul>
      ),
    },
  ];

  return (
    <>
      {blocks.map((b, i) => (
        <div
          key={b.title}
          className={`insight-card card${justGenerated ? " insight-reveal" : ""}`}
          style={justGenerated ? { animationDelay: `${i * 80}ms` } : undefined}
        >
          <h4>{b.title}</h4>
          {b.body}
        </div>
      ))}
    </>
  );
}
