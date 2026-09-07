"""
SIGAP Kopdes - Model Prediksi Risiko (Step 4)
================================================
Melatih model klasifikasi ringan (regresi logistik) untuk memprediksi
probabilitas sebuah koperasi berstatus KRITIS 3 bulan ke depan, berdasarkan
skor & TREN dari engine step 3 -- bukan snapshot skor saat ini saja.

Data pelatihan: pasangan (periode_t, periode_t+3) yang KEDUANYA tersedia di
histori (Mar->Jun, Apr->Jul, Mei->Agu) -> hingga 3 x 156 = 468 contoh.
Karena datanya simulasi & jumlahnya terbatas, metrik evaluasi di sini
INDIKATIF untuk keperluan prototipe -- bukan klaim validasi produksi siap
pakai. Ini penting disebutkan apa adanya ke juri, bukan disamarkan.

Fitur: skor_komposit, skor_transaksi, skor_stok, skor_pelaporan (saat ini),
       delta_1bln, delta_2bln (perubahan skor komposit 1 & 2 bulan terakhir)
Target: kategori == "Kritis" pada t+3 (biner)

Setelah dilatih, model diterapkan ke SEMUA baris skor_kesehatan (bukan cuma
periode terbaru) supaya dashboard selalu punya angka prediksi_risiko_3bln,
apa pun periode yang sedang dilihat pengguna.

Usage:
    python predict_risk.py
Output:
    ../data/output/sigap_kopdes.db      -> skor_kesehatan.prediksi_risiko_3bln terisi
    ../data/output/model_risiko.joblib  -> model terlatih, dipakai lagi di step 6 (API)
"""
import os
import sqlite3
import joblib
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, roc_auc_score

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "..", "data", "output")
DB_PATH = os.path.join(DATA_DIR, "sigap_kopdes.db")
MODEL_PATH = os.path.join(DATA_DIR, "model_risiko.joblib")

GAP_BULAN = 3
FITUR = ["skor_komposit", "skor_transaksi", "skor_stok", "skor_pelaporan", "delta_1bln", "delta_2bln"]


def load_skor():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM skor_kesehatan", conn)
    conn.close()
    for c in ["skor_transaksi", "skor_stok", "skor_pelaporan", "skor_komposit"]:
        df[c] = pd.to_numeric(df[c])
    return df.sort_values(["koperasi_id", "periode"]).reset_index(drop=True)


def tambah_fitur_tren(df):
    df = df.copy()
    df["delta_1bln"] = df.groupby("koperasi_id")["skor_komposit"].diff(1).fillna(0)
    df["delta_2bln"] = df.groupby("koperasi_id")["skor_komposit"].diff(2).fillna(0)
    return df


def geser_periode(p, n):
    """'2026-03' + 3 -> '2026-06'. Data kita semua satu tahun, jadi cukup
    aritmatika bulan sederhana tanpa perlu library tanggal eksternal."""
    y, m = map(int, p.split("-"))
    m += n
    y += (m - 1) // 12
    m = (m - 1) % 12 + 1
    return f"{y:04d}-{m:02d}"


def susun_dataset_latih(df):
    periode_semua = sorted(df["periode"].unique())
    baris = []
    for p in periode_semua:
        p_target = geser_periode(p, GAP_BULAN)
        if p_target not in periode_semua:
            continue  # belum ada "jawaban" GAP_BULAN ke depan utk periode ini
        sekarang = df[df["periode"] == p].set_index("koperasi_id")
        target = df[df["periode"] == p_target].set_index("koperasi_id")
        bersama = sekarang.index.intersection(target.index)
        for kid in bersama:
            baris.append({
                **{f: sekarang.loc[kid, f] for f in FITUR},
                "target_kritis": 1 if target.loc[kid, "kategori"] == "Kritis" else 0,
            })
    return pd.DataFrame(baris)


def latih_model(data_latih):
    X, y = data_latih[FITUR], data_latih["target_kritis"]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y
    )
    model = LogisticRegression(max_iter=1000, class_weight="balanced")
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]
    print(f"Data latih: {len(X_train)} contoh, data uji: {len(X_test)} contoh "
          f"({y.mean()*100:.0f}% berlabel Kritis di seluruh dataset)")
    print(f"Akurasi (data uji): {accuracy_score(y_test, y_pred):.2f}")
    try:
        print(f"ROC-AUC (data uji): {roc_auc_score(y_test, y_proba):.2f}")
    except ValueError:
        pass
    print("\nKoefisien model (arah pengaruh tiap fitur; positif = menaikkan risiko):")
    for fitur, koef in zip(FITUR, model.coef_[0]):
        print(f"  {fitur:16s} {koef:+.3f}")
    return model


def terapkan_ke_semua(df, model):
    df = df.copy()
    proba = model.predict_proba(df[FITUR])[:, 1]
    df["prediksi_risiko_3bln"] = (proba * 100).round(1)
    return df.drop(columns=["delta_1bln", "delta_2bln"])


def simpan(df, model):
    conn = sqlite3.connect(DB_PATH)
    df.to_sql("skor_kesehatan", conn, if_exists="replace", index=False)
    conn.close()
    df.to_csv(os.path.join(DATA_DIR, "skor_kesehatan.csv"), index=False)
    joblib.dump(model, MODEL_PATH)


def main():
    df = tambah_fitur_tren(load_skor())

    data_latih = susun_dataset_latih(df)
    model = latih_model(data_latih)

    df_hasil = terapkan_ke_semua(df, model)
    simpan(df_hasil, model)

    periode_terbaru = df_hasil["periode"].max()
    terbaru = df_hasil[df_hasil["periode"] == periode_terbaru]
    print(f"\nprediksi_risiko_3bln terisi untuk seluruh {len(df_hasil)} baris skor_kesehatan.")
    print(f"5 koperasi dengan proyeksi risiko tertinggi (periode {periode_terbaru}):")
    kolom = ["koperasi_id", "kategori", "skor_komposit", "prediksi_risiko_3bln"]
    print(terbaru.sort_values("prediksi_risiko_3bln", ascending=False)[kolom].head(5).to_string(index=False))
    print(f"\nModel tersimpan ke: {MODEL_PATH}")


if __name__ == "__main__":
    main()
