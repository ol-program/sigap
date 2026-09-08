"""
SIGAP Kopdes - Engine Skor Kesehatan (Step 3)

Membaca data mentah (transaksi, stok, laporan) hasil step 2, menghitung skor
kesehatan komposit per koperasi per periode (bulan), menyimpannya ke tabel
skor_kesehatan, dan menerbitkan notifikasi otomatis.

Metodologi (bobot & ambang di konstanta bawah):
  skor_transaksi  = rata-rata peringkat persentil jumlah & total nilai
                     transaksi, relatif terhadap koperasi lain di periode
                     yang sama (persentil dipakai, bukan interpolasi linear,
                     supaya tahan terhadap distribusi nilai yang skewed)
  skor_stok       = peringkat persentil jumlah unit stok
  skor_pelaporan  = persen_kelengkapan laporan (0-100, dipakai langsung)
  skor_komposit   = rata-rata terbobot ketiga skor di atas
  kategori        = Sehat (>=70) / Waspada (40-69) / Kritis (<40)

Skor bersifat relatif terhadap populasi koperasi yang dipantau, bukan skala
absolut. prediksi_risiko_3bln dikosongkan (None) di sini -- dihitung step 4.

Usage:
    python compute_scores.py
Output:
    ../data/output/sigap_kopdes.db     -> tabel skor_kesehatan & notifikasi
    ../data/output/skor_kesehatan.csv, notifikasi.csv
"""
import os
import sqlite3
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "..", "data", "output")
DB_PATH = os.path.join(DATA_DIR, "sigap_kopdes.db")

# --- parameter yang bisa disetel ---------------------------------------
BOBOT = {"transaksi": 1 / 3, "stok": 1 / 3, "pelaporan": 1 / 3}
BATAS_SEHAT = 70
BATAS_WASPADA = 40
TURUN_SIGNIFIKAN = 5  # poin -- pemicu notifikasi jika skor turun >= ini
# -------------------------------------------------------------------------


def load_tables():
    # generate_data.py menulis semua kolom SQLite sebagai TEXT, jadi kolom
    # numerik dikonversi eksplisit di bawah.
    conn = sqlite3.connect(DB_PATH)
    transaksi = pd.read_sql("SELECT * FROM transaksi", conn)
    stok = pd.read_sql("SELECT * FROM stok", conn)
    laporan = pd.read_sql("SELECT * FROM laporan", conn)
    conn.close()

    transaksi["nilai_rupiah"] = pd.to_numeric(transaksi["nilai_rupiah"])
    stok["jumlah_unit"] = pd.to_numeric(stok["jumlah_unit"])
    stok["nilai_rupiah"] = pd.to_numeric(stok["nilai_rupiah"])
    laporan["persen_kelengkapan"] = pd.to_numeric(laporan["persen_kelengkapan"])
    return transaksi, stok, laporan


def peringkat_persentil(basis, kolom):
    """Skor 0-100 berbasis peringkat kolom dalam periode yang sama."""
    return basis.groupby("periode")[kolom].rank(pct=True, method="average") * 100


def siapkan_basis(transaksi, stok, laporan):
    """Gabungkan transaksi/stok/laporan jadi satu tabel (koperasi_id x
    periode), memakai laporan sebagai kerangka acuan (dikirim tiap bulan)."""
    transaksi = transaksi.copy()
    transaksi["periode"] = transaksi["tanggal"].str.slice(0, 7)
    trans_agg = transaksi.groupby(["koperasi_id", "periode"]).agg(
        jumlah_transaksi=("transaksi_id", "count"),
        total_nilai_transaksi=("nilai_rupiah", "sum"),
    ).reset_index()

    stok = stok.copy()
    stok["periode"] = stok["tanggal_pencatatan"].str.slice(0, 7)
    stok_agg = stok[["koperasi_id", "periode", "jumlah_unit"]]

    basis = laporan[["koperasi_id", "periode", "persen_kelengkapan"]].copy()
    basis = basis.merge(trans_agg, on=["koperasi_id", "periode"], how="left")
    basis = basis.merge(stok_agg, on=["koperasi_id", "periode"], how="left")
    basis[["jumlah_transaksi", "total_nilai_transaksi", "jumlah_unit"]] = (
        basis[["jumlah_transaksi", "total_nilai_transaksi", "jumlah_unit"]].fillna(0)
    )
    return basis


def kategorikan(skor):
    if skor >= BATAS_SEHAT:
        return "Sehat"
    if skor >= BATAS_WASPADA:
        return "Waspada"
    return "Kritis"


def hitung_skor(basis):
    df = basis.copy()
    pr_freq = peringkat_persentil(df, "jumlah_transaksi")
    pr_nilai = peringkat_persentil(df, "total_nilai_transaksi")
    df["skor_transaksi"] = ((pr_freq + pr_nilai) / 2).round(1)
    df["skor_stok"] = peringkat_persentil(df, "jumlah_unit").round(1)
    df["skor_pelaporan"] = df["persen_kelengkapan"].round(1)
    df["skor_komposit"] = (
        df["skor_transaksi"] * BOBOT["transaksi"]
        + df["skor_stok"] * BOBOT["stok"]
        + df["skor_pelaporan"] * BOBOT["pelaporan"]
    ).round(1)
    df["kategori"] = df["skor_komposit"].apply(kategorikan)
    df["skor_id"] = "SKR-" + df["koperasi_id"] + "-" + df["periode"]
    df["prediksi_risiko_3bln"] = None  # diisi step 4

    kolom_akhir = ["skor_id", "koperasi_id", "periode", "skor_transaksi", "skor_stok",
                   "skor_pelaporan", "skor_komposit", "kategori", "prediksi_risiko_3bln"]
    return df[kolom_akhir].sort_values(["koperasi_id", "periode"]).reset_index(drop=True)


def terbitkan_notifikasi(df_skor):
    df = df_skor.sort_values(["koperasi_id", "periode"]).copy()
    df["skor_sebelumnya"] = df.groupby("koperasi_id")["skor_komposit"].shift(1)
    df["delta"] = df["skor_komposit"] - df["skor_sebelumnya"]

    baris_notif, nid = [], 1
    for _, r in df.iterrows():
        alert = None
        if r["kategori"] == "Kritis":
            alert = "Skor masuk kategori Kritis"
        elif pd.notna(r["delta"]) and r["delta"] <= -TURUN_SIGNIFIKAN:
            alert = f"Skor turun {abs(r['delta']):.1f} poin dari bulan sebelumnya"
        if alert:
            baris_notif.append({
                "notifikasi_id": f"NTF-{nid:06d}",
                "koperasi_id": r["koperasi_id"],
                "tanggal": f"{r['periode']}-28",
                "jenis_alert": alert,
                "status_tindak_lanjut": "Baru",
            })
            nid += 1
    return pd.DataFrame(baris_notif)


def simpan(df_skor, df_notif):
    conn = sqlite3.connect(DB_PATH)
    df_skor.to_sql("skor_kesehatan", conn, if_exists="replace", index=False)
    df_notif.to_sql("notifikasi", conn, if_exists="replace", index=False)
    conn.close()
    df_skor.to_csv(os.path.join(DATA_DIR, "skor_kesehatan.csv"), index=False)
    df_notif.to_csv(os.path.join(DATA_DIR, "notifikasi.csv"), index=False)


def main():
    transaksi, stok, laporan = load_tables()
    basis = siapkan_basis(transaksi, stok, laporan)
    df_skor = hitung_skor(basis)
    df_notif = terbitkan_notifikasi(df_skor)
    simpan(df_skor, df_notif)

    periode_terbaru = df_skor["periode"].max()
    terbaru = df_skor[df_skor["periode"] == periode_terbaru]
    print(f"Skor dihitung: {df_skor['koperasi_id'].nunique()} koperasi x {df_skor['periode'].nunique()} periode "
          f"({len(df_skor)} baris).")
    print(f"Periode terbaru ({periode_terbaru}): "
          f"Sehat={ (terbaru['kategori'] == 'Sehat').sum() }, "
          f"Waspada={ (terbaru['kategori'] == 'Waspada').sum() }, "
          f"Kritis={ (terbaru['kategori'] == 'Kritis').sum() }")
    print(f"Notifikasi diterbitkan: {len(df_notif)}")
    print()
    print("5 koperasi dengan skor terendah (periode terbaru):")
    kolom = ["koperasi_id", "skor_transaksi", "skor_stok", "skor_pelaporan", "skor_komposit", "kategori"]
    print(terbaru.sort_values("skor_komposit")[kolom].head(5).to_string(index=False))
    print()
    print(f"Tersimpan ke {DB_PATH} (tabel skor_kesehatan, notifikasi) dan CSV di {DATA_DIR}/")


if __name__ == "__main__":
    main()
