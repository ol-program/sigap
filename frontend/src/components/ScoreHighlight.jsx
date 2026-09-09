import StatusBadge from "./StatusBadge.jsx";
import InfoTooltip from "./InfoTooltip.jsx";
import { statusHex } from "../statusColors.js";

const RADIUS = 54;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

// Ring pakai warna status sebagai aksen; teks tetap token biasa, identitas
// kategori dibawa oleh StatusBadge di sampingnya.
export default function ScoreHighlight({ skor, kategori, previousSkor, prediksiRisiko }) {
  const pct = Math.max(0, Math.min(100, skor ?? 0));
  const offset = CIRCUMFERENCE * (1 - pct / 100);
  const color = statusHex(kategori);

  const delta = previousSkor != null && skor != null ? +(skor - previousSkor).toFixed(1) : null;

  return (
    <div className="card score-highlight-card">
      <div className="score-highlight-inner">
        <div className="score-ring-wrap" role="img" aria-label={`Skor kelayakan komposit ${skor ?? "-"} dari 100, kategori ${kategori ?? "-"}`}>
          <svg viewBox="0 0 120 120" className="score-ring">
            <circle cx="60" cy="60" r={RADIUS} className="score-ring-track" strokeWidth="10" fill="none" />
            <circle
              cx="60"
              cy="60"
              r={RADIUS}
              stroke={color}
              strokeWidth="10"
              fill="none"
              strokeLinecap="round"
              strokeDasharray={CIRCUMFERENCE}
              strokeDashoffset={skor != null ? offset : CIRCUMFERENCE}
              transform="rotate(-90 60 60)"
              className="score-ring-progress"
            />
          </svg>
          <div className="score-ring-center">
            <span className="score-value">{skor ?? "-"}</span>
            <span className="score-max">/ 100</span>
          </div>
        </div>

        <div className="score-highlight-meta">
          <div className="score-highlight-label">
            Skor Kelayakan Komposit
            <InfoTooltip text="Rata-rata tertimbang skor transaksi, stok, dan pelaporan bulan ini. Skala 0-100, relatif terhadap koperasi lain yang dipantau." />
          </div>
          <div className="score-highlight-row">
            <StatusBadge kategori={kategori} />
            {delta != null && (
              <span className={`score-delta ${delta > 0 ? "up" : delta < 0 ? "down" : ""}`}>
                {delta > 0 ? "▲" : delta < 0 ? "▼" : "–"} {Math.abs(delta)} dari bulan lalu
              </span>
            )}
          </div>
          {prediksiRisiko != null && (
            <div className="score-highlight-secondary">
              Proyeksi risiko Kritis 3 bulan
              <InfoTooltip text="Peluang koperasi ini jadi Kritis 3 bulan lagi, dari model prediktif. Indikatif (data simulasi), bukan validasi produksi." />
              : <strong>{prediksiRisiko}%</strong>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
