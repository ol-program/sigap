import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { MapContainer, TileLayer, CircleMarker, Tooltip, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { api } from "../api.js";
import { statusHex } from "../statusColors.js";

const INDONESIA_CENTER = [-2.5, 118];

// react-leaflet tidak re-center otomatis kalau center berubah setelah mount.
function FlyTo({ center, zoom }) {
  const map = useMap();
  useEffect(() => {
    map.flyTo(center, zoom, { duration: 0.6 });
  }, [center, zoom, map]);
  return null;
}

function radiusFor(jumlah) {
  return Math.min(36, 9 + Math.sqrt(jumlah || 1) * 4);
}

// Peta drill-down provinsi -> kabupaten/kota -> koperasi individual.
export default function PetaWilayah() {
  const navigate = useNavigate();
  const [level, setLevel] = useState("provinsi"); // provinsi | kabupaten | koperasi
  const [provinsiAktif, setProvinsiAktif] = useState(null); // {nama, latitude, longitude}
  const [kabupatenAktif, setKabupatenAktif] = useState(null);
  const [rows, setRows] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    setRows(null);
    setError(null);
    if (level === "provinsi") {
      api.petaProvinsi().then((d) => setRows(d.provinsi)).catch((e) => setError(e.message));
    } else if (level === "kabupaten" && provinsiAktif) {
      api.petaKabupaten({ provinsi: provinsiAktif.nama }).then((d) => setRows(d.kabupaten)).catch((e) => setError(e.message));
    } else if (level === "koperasi" && kabupatenAktif) {
      api.koperasiList({ kabupaten_kota: kabupatenAktif.nama }).then(setRows).catch((e) => setError(e.message));
    }
  }, [level, provinsiAktif, kabupatenAktif]);

  const center = level === "koperasi" ? [kabupatenAktif.latitude, kabupatenAktif.longitude]
    : level === "kabupaten" ? [provinsiAktif.latitude, provinsiAktif.longitude]
    : INDONESIA_CENTER;
  const zoom = level === "koperasi" ? 11 : level === "kabupaten" ? 8 : 5;

  return (
    <div className="card" style={{ marginBottom: 24, padding: 16 }}>
      <h4 style={{ marginTop: 0, marginBottom: 4 }}>Peta Sebaran Koperasi</h4>
      <p className="page-desc" style={{ marginBottom: 12 }}>
        Agregat kondisi kelayakan koperasi per wilayah. Klik titik untuk lihat lebih detail.
      </p>

      <div className="breadcrumb">
        <a onClick={() => { setLevel("provinsi"); setProvinsiAktif(null); setKabupatenAktif(null); }} style={{ cursor: "pointer" }}>
          Indonesia
        </a>
        {provinsiAktif && (
          <>
            {" / "}
            <a onClick={() => { setLevel("kabupaten"); setKabupatenAktif(null); }} style={{ cursor: "pointer" }}>
              {provinsiAktif.nama}
            </a>
          </>
        )}
        {kabupatenAktif && <>{" / "}{kabupatenAktif.nama}</>}
      </div>

      {error && <div className="error-state">{error}</div>}

      <div style={{ borderRadius: 8, overflow: "hidden", position: "relative", border: "1px solid var(--border)" }}>
        <div style={{
          position: "absolute", top: 12, right: 12, zIndex: 1000,
          background: "var(--surface-1)", border: "1px solid var(--border)",
          borderRadius: 8, padding: "8px 12px", fontSize: 12,
        }}>
          <div style={{ marginBottom: 4, color: "var(--text-secondary)" }}>Kategori agregat</div>
          {["Sehat", "Waspada", "Kritis"].map((k) => (
            <div key={k} style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 2 }}>
              <span style={{ width: 10, height: 10, borderRadius: "50%", background: statusHex(k), display: "inline-block" }} />
              {k}
            </div>
          ))}
        </div>

        <MapContainer center={INDONESIA_CENTER} zoom={5} style={{ height: 460, width: "100%" }} scrollWheelZoom>
          <FlyTo center={center} zoom={zoom} />
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          {level !== "koperasi" && rows && rows.map((r) => (
            <CircleMarker
              key={r.nama}
              center={[r.latitude, r.longitude]}
              radius={radiusFor(r.jumlah_koperasi)}
              pathOptions={{ color: statusHex(r.kategori_agregat), fillColor: statusHex(r.kategori_agregat), fillOpacity: 0.55, weight: 2 }}
              eventHandlers={{
                click: () => {
                  if (level === "provinsi") { setProvinsiAktif(r); setLevel("kabupaten"); }
                  else { setKabupatenAktif(r); setLevel("koperasi"); }
                },
              }}
            >
              <Tooltip direction="top">
                <strong>{r.nama}</strong><br />
                {r.jumlah_koperasi} koperasi &middot; rata-rata skor {r.rata_rata_skor ?? "-"} ({r.kategori_agregat ?? "-"})<br />
                Sehat {r.per_kategori.Sehat} &middot; Waspada {r.per_kategori.Waspada} &middot; Kritis {r.per_kategori.Kritis}
              </Tooltip>
            </CircleMarker>
          ))}

          {level === "koperasi" && rows && rows.map((k) => (
            k.latitude != null && (
              <CircleMarker
                key={k.koperasi_id}
                center={[parseFloat(k.latitude), parseFloat(k.longitude)]}
                radius={8}
                pathOptions={{ color: statusHex(k.kategori), fillColor: statusHex(k.kategori), fillOpacity: 0.7, weight: 1.5 }}
                eventHandlers={{ click: () => navigate(`/koperasi/${k.koperasi_id}`) }}
              >
                <Tooltip direction="top">
                  <strong>{k.nama_koperasi}</strong><br />
                  Skor {k.skor_komposit ?? "-"} ({k.kategori ?? "-"})<br />
                  Klik untuk lihat detail
                </Tooltip>
              </CircleMarker>
            )
          ))}
        </MapContainer>
      </div>
    </div>
  );
}
