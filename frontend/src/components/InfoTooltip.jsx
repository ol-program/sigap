// Ikon "i" kecil dengan penjelasan singkat saat hover/fokus -- dipakai di
// samping label/angka yang artinya tidak jelas dari nama kolom saja (mis.
// "Skor komposit", "Kategori"). Untuk penjelasan lengkap, arahkan ke
// halaman "Kriteria & Metodologi" lewat prop `linkText` opsional.
export default function InfoTooltip({ text }) {
  return (
    <span className="info-tooltip" tabIndex={0}>
      <span className="info-tooltip-icon" aria-hidden="true">ⓘ</span>
      <span className="info-tooltip-text" role="tooltip">{text}</span>
    </span>
  );
}
