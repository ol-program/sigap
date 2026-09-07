import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api.js";
import ScoreHighlight from "../components/ScoreHighlight.jsx";
import ScoreTrendChart from "../components/ScoreTrendChart.jsx";
import InfoTooltip from "../components/InfoTooltip.jsx";
import AiInsightCard from "../components/AiInsightCard.jsx";

export default function KoperasiDetailPage() {
  const { koperasiId } = useParams();
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    setDetail(null);
    setError(null);
    api.koperasiDetail(koperasiId).then(setDetail).catch((e) => setError(e.message));
  }, [koperasiId]);

  if (error) return <div className="error-state">{error}</div>;
  if (!detail) return <div className="loading-state">Memuat detail koperasi...</div>;

  const { koperasi, histori_skor, ai_insight_terbaru } = detail;
  const terbaru = histori_skor[histori_skor.length - 1];
  const sebelumnya = histori_skor.length > 1 ? histori_skor[histori_skor.length - 2] : null;

  return (
    <div>
      <div className="breadcrumb"><Link to="/koperasi">&larr; Daftar Koperasi</Link></div>
      <h2>{koperasi.nama_koperasi}</h2>
      <p className="page-desc">
        {koperasi.koperasi_id} &middot; {koperasi.desa_kelurahan}, {koperasi.kecamatan}, {koperasi.kabupaten_kota}, {koperasi.provinsi}
        {terbaru?.periode ? <> &middot; periode {terbaru.periode}</> : null}
        {" "}&middot; <Link to="/metodologi">arti istilah di halaman ini</Link>
      </p>

      {terbaru && (
        <ScoreHighlight
          skor={terbaru.skor_komposit}
          kategori={terbaru.kategori}
          previousSkor={sebelumnya?.skor_komposit}
          prediksiRisiko={terbaru.prediksi_risiko_3bln}
        />
      )}

      <div className="detail-grid">
        <div className="card">
          <dl className="kv-list" style={{ margin: 0 }}>
            <dt>Jenis usaha</dt>
            <dd>{koperasi.jenis_usaha}</dd>

            <dt>Jumlah anggota</dt>
            <dd>{koperasi.jumlah_anggota}</dd>

            <dt>Status operasional</dt>
            <dd>{koperasi.status_operasional}</dd>

            <dt>PMO penanggung jawab</dt>
            <dd>{koperasi.pmo_penanggung_jawab}</dd>

            <dt>
              Status kemajuan desa (IDM)
              <InfoTooltip text="Indeks resmi Kemendes PDTT untuk kondisi WILAYAH (bukan kondisi koperasi ini) -- dipakai sebagai konteks rekomendasi AI Insight." />
            </dt>
            <dd>{koperasi.status_idm} (skor {koperasi.skor_idm})</dd>

            <dt>Mata pencaharian dominan wilayah</dt>
            <dd>{koperasi.mata_pencaharian_dominan}</dd>

            <dt>Akses pusat perdagangan</dt>
            <dd>{koperasi.akses_pusat_perdagangan}</dd>
          </dl>
        </div>

        <div>
          <div className="card" style={{ marginBottom: 16 }}>
            <h4 style={{ marginTop: 0 }}>Tren skor kesehatan</h4>
            <ScoreTrendChart data={histori_skor} />
          </div>

          <div className="card">
            <h4 style={{ marginTop: 0 }}>AI Insight &amp; Rekomendasi</h4>
            <AiInsightCard koperasiId={koperasi.koperasi_id} initial={ai_insight_terbaru} />
          </div>
        </div>
      </div>
    </div>
  );
}
