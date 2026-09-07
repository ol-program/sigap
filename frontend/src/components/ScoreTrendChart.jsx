import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";

const SERIES = [
  { key: "skor_komposit", label: "Komposit", color: "var(--series-1)", width: 2.5 },
  { key: "skor_transaksi", label: "Transaksi", color: "var(--series-2)", width: 2 },
  { key: "skor_stok", label: "Stok", color: "var(--series-3)", width: 2 },
  { key: "skor_pelaporan", label: "Pelaporan", color: "var(--series-4)", width: 2 },
];

// Satu sumbu Y (0-100, skala skor yang sama untuk keempat seri) -- lihat
// skill dataviz: dua ukuran berbeda skala tidak pernah dipaksa jadi dual-axis.
export default function ScoreTrendChart({ data }) {
  return (
    <ResponsiveContainer width="100%" height={280}>
      <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
        <CartesianGrid stroke="var(--gridline)" vertical={false} />
        <XAxis
          dataKey="periode"
          stroke="var(--baseline)"
          tick={{ fill: "var(--text-muted)", fontSize: 12 }}
        />
        <YAxis
          domain={[0, 100]}
          stroke="var(--baseline)"
          tick={{ fill: "var(--text-muted)", fontSize: 12 }}
          width={32}
        />
        <Tooltip
          contentStyle={{
            background: "var(--surface-1)",
            border: "1px solid var(--border)",
            borderRadius: 8,
            fontSize: 13,
          }}
          labelStyle={{ color: "var(--text-primary)" }}
        />
        <Legend wrapperStyle={{ fontSize: 12, color: "var(--text-secondary)" }} />
        {SERIES.map((s) => (
          <Line
            key={s.key}
            type="monotone"
            dataKey={s.key}
            name={s.label}
            stroke={s.color}
            strokeWidth={s.width}
            dot={{ r: 3 }}
            activeDot={{ r: 5 }}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
