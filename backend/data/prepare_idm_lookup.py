"""
SIGAP Kopdes - Ekstraksi Data IDM Asli (persiapan untuk step 2)

Script sekali-jalan yang menyaring baris relevan dari data resmi Indeks Desa
Membangun (IDM) 2024, Kemendes PDTT (file Excel) ke CSV kecil
(idm_2024_lookup.csv) yang dibaca generate_data.py. Dipisah dari
generate_data.py supaya pipeline reguler tidak butuh openpyxl atau membaca
file Excel 7+ MB tiap kali data di-generate ulang.

Cuma 13 dari 21 kabupaten/kota di WILAYAH_SEED yang dapat data asli -- IDM
secara definisi hanya mencakup desa (kewenangan Kemendes PDTT), bukan
kelurahan (wilayah kota, kewenangan Kemendagri), jadi 8 kabupaten/kota
berstatus "Kota" otomatis tidak ada di data IDM. Data ini per 2024, bukan
tahun berjalan.

Usage:
    python prepare_idm_lookup.py "/path/ke/indeks-desa-membangun-....xlsx"

Output:
    idm_2024_lookup.csv (di folder yang sama dengan script ini) --
    kolom: kabupaten_kota, kecamatan, desa, dimensi_sosial, dimensi_ekonomi,
    dimensi_lingkungan, skor_idm, status_idm
"""
import os
import sys
import csv

HERE = os.path.dirname(os.path.abspath(__file__))
OUTPUT_CSV = os.path.join(HERE, "idm_2024_lookup.csv")

# kabupaten_kota (gaya WILAYAH_SEED) -> (NAMA_PROVINSI, NAMA_KABUPATEN) persis
# seperti di file IDM sumber. Hanya 13 kabupaten -- lihat docstring modul.
KABUPATEN_MAP = {
    "Kab. Bandung": ("JAWA BARAT", "BANDUNG"),
    "Kab. Cianjur": ("JAWA BARAT", "CIANJUR"),
    "Kab. Malang": ("JAWA TIMUR", "MALANG"),
    "Kab. Sidoarjo": ("JAWA TIMUR", "SIDOARJO"),
    "Kab. Karanganyar": ("JAWA TENGAH", "KARANGANYAR"),
    "Kab. Semarang": ("JAWA TENGAH", "SEMARANG"),
    "Kab. Deli Serdang": ("SUMATERA UTARA", "DELI SERDANG"),
    "Kab. Gowa": ("SULAWESI SELATAN", "GOWA"),
    "Kab. Bantaeng": ("SULAWESI SELATAN", "BANTAENG"),
    "Kab. Kupang": ("NUSA TENGGARA TIMUR", "KUPANG"),
    "Kab. Sumba Timur": ("NUSA TENGGARA TIMUR", "SUMBA TIMUR"),
    "Kab. Kutai Kartanegara": ("KALIMANTAN TIMUR", "KUTAI KARTANEGARA"),
    "Kab. Agam": ("SUMATERA BARAT", "AGAM"),
}
# baris terbalik untuk lookup cepat: (provinsi, kabupaten) -> kabupaten_kota kita
REVERSE_MAP = {v: k for k, v in KABUPATEN_MAP.items()}


def main():
    if len(sys.argv) != 2:
        print("Usage: python prepare_idm_lookup.py <path-ke-file-idm.xlsx>")
        sys.exit(1)
    xlsx_path = sys.argv[1]
    if not os.path.exists(xlsx_path):
        print(f"File tidak ditemukan: {xlsx_path}")
        sys.exit(1)

    import openpyxl  # hanya dependency script ini, TIDAK ditambah ke requirements.txt
    wb = openpyxl.load_workbook(xlsx_path, data_only=True, read_only=True)
    ws = wb["IDM 2024"]

    hasil = []
    for r in ws.iter_rows(min_row=2, values_only=True):
        # kolom: 0 KODE_PROV, 1 NAMA_PROVINSI, 2 KODE_KAB, 3 NAMA_KABUPATEN,
        # 4 KODE_KEC, 5 NAMA_KECAMATAN, 6 KODE_DESA, 7 NAMA_DESA,
        # 8 IKS_2024, 9 IKE_2024, 10 IKL_2024, 11 NILAI_IDM_2024, 12 STATUS_IDM_2024
        key = (r[1], r[3])
        kabupaten_kota = REVERSE_MAP.get(key)
        if kabupaten_kota is None:
            continue
        kecamatan, desa = r[5], r[7]
        iks, ike, ikl, nilai, status = r[8], r[9], r[10], r[11], r[12]
        if not desa or not kecamatan or status is None:
            continue
        hasil.append({
            "kabupaten_kota": kabupaten_kota,
            "kecamatan": kecamatan.title(),
            "desa": desa.title(),
            "dimensi_sosial": iks,
            "dimensi_ekonomi": ike,
            "dimensi_lingkungan": ikl,
            "skor_idm": nilai,
            "status_idm": status.title(),
        })

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(hasil[0].keys()))
        writer.writeheader()
        writer.writerows(hasil)

    per_kab = {}
    for row in hasil:
        per_kab[row["kabupaten_kota"]] = per_kab.get(row["kabupaten_kota"], 0) + 1
    print(f"Tersimpan {len(hasil)} desa ke {OUTPUT_CSV}")
    for kab, n in sorted(per_kab.items()):
        print(f"  {kab}: {n} desa")
    kurang = set(KABUPATEN_MAP) - set(per_kab)
    if kurang:
        print(f"PERINGATAN: tidak ada data untuk {kurang} -- generate_data.py akan gagal untuk kabupaten ini.")


if __name__ == "__main__":
    main()
