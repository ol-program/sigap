const STATUS_MAP = {
  Sehat: { cls: "good", label: "Sehat" },
  Waspada: { cls: "warning", label: "Waspada" },
  Kritis: { cls: "critical", label: "Kritis" },
};

// Status TIDAK ditandai dengan warna saja -- selalu dot + label teks
// (lihat skill dataviz: warning/serious sub-3:1 di light surface).
export default function StatusBadge({ kategori }) {
  const info = STATUS_MAP[kategori] || { cls: "warning", label: kategori || "-" };
  return (
    <span className="status-badge">
      <span className={`status-dot ${info.cls}`} />
      {info.label}
    </span>
  );
}
