// Warna status TETAP (tidak ikut tema terang/gelap) -- dipakai di peta karena
// tile OpenStreetMap selalu berlatar terang, dan di StatusBadge/CSS lewat
// custom property yang senilai. Satu sumber supaya dua tempat itu konsisten.
export const STATUS_HEX = {
  Sehat: "#0ca30c",
  Waspada: "#fab219",
  Kritis: "#d03b3b",
};

export function statusHex(kategori) {
  return STATUS_HEX[kategori] || "#898781";
}
