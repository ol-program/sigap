"""
SIGAP Kopdes - Generator Data Simulasi
========================================
Menghasilkan data simulasi mengikuti skema (lihat skema_data_sigap_kopdes.mermaid):
WILAYAH, PROFIL_WILAYAH, KOPERASI, TRANSAKSI, STOK, LAPORAN

PENTING: seluruh data di sini SIMULASI untuk keperluan prototipe/demo kompetisi,
bukan data KDMP asli. PROFIL_WILAYAH mensimulasikan struktur Indeks Desa
Membangun (IDM, Kemendes PDTT) -- lihat komentar di dekat konstanta
STATUS_IDM_WEIGHT. Setiap koperasi diberi "profil kesehatan" tersembunyi
(_tier, _trend) yang HANYA dipakai untuk membangkitkan pola transaksi/stok/
laporan yang realistis -- field ini tidak ditulis ke tabel KOPERASI karena
bukan bagian dari skema resmi. Skor kesehatan sesungguhnya akan dihitung
dari data mentah ini di step 3 (engine skor), bukan diinput langsung.

WILAYAH juga menyimpan latitude/longitude (lihat KABUPATEN_KOTA_COORD) untuk
kebutuhan peta di dashboard (step 7) -- titik pusat kabupaten/kota ASLI
(provinsi & kabupaten/kota di WILAYAH_SEED memang nama wilayah Indonesia
sungguhan, hanya desa/kelurahan di bawahnya yang fiktif) dengan sebaran acak
kecil per desa supaya titik-titiknya tidak bertumpuk di satu koordinat.

PROFIL_WILAYAH TIDAK LAGI SEPENUHNYA SIMULASI: untuk 13 dari 21 kabupaten/kota
di WILAYAH_SEED yang berstatus "Kabupaten", nama desa + dimensi sosial/
ekonomi/lingkungan + status/skor IDM diambil dari data ASLI Indeks Desa
Membangun 2024 (Kemendes PDTT, hasil pemutakhiran) -- lihat
`idm_2024_lookup.csv` & `prepare_idm_lookup.py`. 8 kabupaten/kota sisanya
berstatus "Kota" TETAP simulasi penuh (nama desa fiktif + IDM disimulasikan
seperti sebelumnya) karena IDM secara definisi hanya mencakup DESA
(kewenangan Kemendes PDTT), bukan KELURAHAN (wilayah kota, kewenangan
Kemendagri) -- bukan keterbatasan yang disembunyikan, tapi cerminan struktur
pemerintahan asli. Field lain di PROFIL_WILAYAH (mata_pencaharian_dominan,
ekonomi_beragam, akses_pusat_perdagangan) TETAP simulasi untuk semua wilayah
karena tidak ada di sumber IDM. Data operasional (TRANSAKSI/STOK/LAPORAN)
tetap 100% simulasi seperti sebelumnya -- KDMP asli belum eksis di data ini.

Usage:
    python generate_data.py

Output (di ./output/):
    sigap_kopdes.db          SQLite, 5 tabel sesuai skema
    wilayah.csv, koperasi.csv, transaksi.csv, stok.csv, laporan.csv
"""
import random
import sqlite3
import csv
import os
from collections import defaultdict
from datetime import date

random.seed(42)  # reproducible antar-run

HERE = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(HERE, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 6 bulan berjalan (Mar-Agu 2026), representasi tanggal akhir tiap bulan
MONTHS = [
    ("2026-03", date(2026, 3, 31)),
    ("2026-04", date(2026, 4, 30)),
    ("2026-05", date(2026, 5, 31)),
    ("2026-06", date(2026, 6, 30)),
    ("2026-07", date(2026, 7, 31)),
    ("2026-08", date(2026, 8, 13)),  # bulan berjalan, belum penuh
]

WILAYAH_SEED = {
    "Jawa Barat": ["Kab. Bandung", "Kab. Cianjur", "Kota Bandung"],
    "Jawa Timur": ["Kota Surabaya", "Kab. Malang", "Kab. Sidoarjo"],
    "Jawa Tengah": ["Kab. Karanganyar", "Kab. Semarang", "Kota Surakarta"],
    "Sumatera Utara": ["Kab. Deli Serdang", "Kota Medan"],
    "Sulawesi Selatan": ["Kab. Gowa", "Kab. Bantaeng", "Kota Makassar"],
    "NTT": ["Kota Kupang", "Kab. Kupang", "Kab. Sumba Timur"],
    "Kalimantan Timur": ["Kota Balikpapan", "Kab. Kutai Kartanegara"],
    "Sumatera Barat": ["Kota Padang", "Kab. Agam"],
}

# Jumlah koperasi (KDMP) RIIL per provinsi, dari dashboard publik SIMKOPDES
# (https://simkopdes.go.id/pers/dashboard, diakses 2026-09-04, status data
# 04/09/2026) -- dipakai untuk MENGKALIBRASI PROPORSI jumlah koperasi
# simulasi antar provinsi (provinsi besar dapat porsi lebih banyak), BUKAN
# untuk menyalin angka aslinya: data operasional tetap 100% simulasi (lihat
# catatan di awal modul), cuma sebarannya sekarang tidak lagi seragam acak
# seperti sebelumnya (dulu tiap kabupaten dapat random.randint(5, 9) yang
# sama, tidak peduli provinsinya Jawa Tengah atau Kalimantan Timur).
SIMKOPDES_JUMLAH_KOPERASI_PROVINSI = {
    "Jawa Barat": 5970,
    "Jawa Timur": 8494,
    "Jawa Tengah": 8524,
    "Sumatera Utara": 6102,
    "Sulawesi Selatan": 3080,
    "NTT": 3452,
    "Kalimantan Timur": 1038,
    "Sumatera Barat": 1270,
}

# Floor tetap per kabupaten + anggaran "ekstra" yang dibagi antar-provinsi
# sesuai proporsi riil di atas -- proporsi MURNI 1:1 ke angka SIMKOPDES akan
# membuat provinsi terkecil (Kalimantan Timur, ~1/8 dari Jawa Tengah) cuma
# kebagian 1-2 koperasi per kabupaten, terlalu tipis untuk pipeline skor &
# prediksi risiko (step 3-4) punya variasi bulanan yang bermakna.
KOPERASI_FLOOR_PER_KABUPATEN = 5
KOPERASI_EXTRA_BUDGET = 90


def _target_koperasi_per_kabupaten():
    """Target jumlah koperasi per kabupaten, dihitung sekali: floor tetap +
    bagian dari KOPERASI_EXTRA_BUDGET yang dibagi rata dalam satu provinsi,
    ditimbang proporsi provinsi itu di SIMKOPDES_JUMLAH_KOPERASI_PROVINSI."""
    total_riil = sum(SIMKOPDES_JUMLAH_KOPERASI_PROVINSI.values())
    target = {}
    for provinsi, kab_list in WILAYAH_SEED.items():
        share = SIMKOPDES_JUMLAH_KOPERASI_PROVINSI[provinsi] / total_riil
        extra_provinsi = round(KOPERASI_EXTRA_BUDGET * share)
        base, sisa = divmod(extra_provinsi, len(kab_list))
        for i, kab in enumerate(kab_list):
            target[kab] = KOPERASI_FLOOR_PER_KABUPATEN + base + (1 if i < sisa else 0)
    return target


TARGET_KOPERASI_PER_KABUPATEN = _target_koperasi_per_kabupaten()

# Titik pusat kabupaten/kota di atas -- PERKIRAAN untuk kebutuhan visualisasi
# peta (step 7: drill-down provinsi -> kabupaten -> koperasi), BUKAN batas
# administratif presisi. kabupaten_kota & provinsi di atas memang nama
# wilayah asli Indonesia (hanya desa/kelurahan di bawahnya yang fiktif),
# jadi titik pusat ini cukup akurat untuk menempatkan marker di peta demo.
KABUPATEN_KOTA_COORD = {
    "Kab. Bandung": (-7.0281, 107.5350),
    "Kab. Cianjur": (-6.8168, 107.1425),
    "Kota Bandung": (-6.9175, 107.6191),
    "Kota Surabaya": (-7.2575, 112.7521),
    "Kab. Malang": (-8.1288, 112.5695),
    "Kab. Sidoarjo": (-7.4478, 112.7183),
    "Kab. Karanganyar": (-7.6011, 110.9670),
    "Kab. Semarang": (-7.1372, 110.4106),
    "Kota Surakarta": (-7.5755, 110.8243),
    "Kab. Deli Serdang": (3.4880, 98.8770),
    "Kota Medan": (3.5952, 98.6722),
    "Kab. Gowa": (-5.2094, 119.6017),
    "Kab. Bantaeng": (-5.5378, 119.9556),
    "Kota Makassar": (-5.1477, 119.4327),
    "Kota Kupang": (-10.1772, 123.6070),
    "Kab. Kupang": (-10.0731, 123.7961),
    "Kab. Sumba Timur": (-9.6567, 120.2601),
    "Kota Balikpapan": (-1.2379, 116.8529),
    "Kab. Kutai Kartanegara": (-0.4009, 117.0114),
    "Kota Padang": (-0.9471, 100.4172),
    "Kab. Agam": (-0.3167, 100.1167),
}
JITTER_DERAJAT = 0.09  # sebaran acak titik desa di sekitar pusat kabupaten (~-10km)

DESA_PREFIX = ["Suka", "Mekar", "Karang", "Cinta", "Tanjung", "Sumber", "Bahagia", "Wono", "Sido", "Panca", "Bumi", "Giri"]
DESA_SUFFIX = ["mulya", "asih", "jaya", "makmur", "sari", "rejo", "agung", "indah", "mukti", "damai", "harjo", "kencana"]
JENIS_USAHA = ["Sembako & Ritel", "Simpan Pinjam", "Pertanian & Agroinput", "Logistik & Distribusi", "Perikanan"]

IDM_LOOKUP_CSV = os.path.join(HERE, "idm_2024_lookup.csv")


def load_idm_pool():
    """Muat desa asli hasil saringan `prepare_idm_lookup.py` (lihat docstring
    modul), dikelompokkan per kabupaten_kota. Kosong (bukan error) kalau
    CSV-nya belum pernah dibuat -- kabupaten yang harusnya dapat data asli
    otomatis jatuh ke fallback simulasi penuh di gen_wilayah_dan_koperasi,
    supaya generate_data.py tetap bisa jalan tanpa file IDM sumber."""
    pool = defaultdict(list)
    if not os.path.exists(IDM_LOOKUP_CSV):
        return pool
    with open(IDM_LOOKUP_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            pool[row["kabupaten_kota"]].append(row)
    return pool


IDM_POOL = load_idm_pool()


def ambil_desa_asli(kab):
    """Pop satu desa ASLI acak (tanpa pengembalian, supaya tidak dipakai dua
    kali di kabupaten yang sama) dari IDM_POOL, atau None kalau kabupaten ini
    tidak punya data asli (kota berbasis kelurahan, atau CSV belum dibuat)."""
    pool = IDM_POOL.get(kab)
    if not pool:
        return None
    idx = random.randrange(len(pool))
    return pool.pop(idx)

# --- profil wilayah (mensimulasikan struktur Indeks Desa Membangun / IDM,
# Kemendes PDTT -- dimensi sosial/ekonomi/lingkungan & 5 status kemajuan
# desa) -- dipakai lapisan rekomendasi produk/promo, TERPISAH dari data
# operasional koperasi di atas, supaya kedua sinyal ini tidak tercampur.
STATUS_IDM_WEIGHT = {"Mandiri": 8, "Maju": 24, "Berkembang": 40, "Tertinggal": 22, "Sangat Tertinggal": 6}
MATA_PENCAHARIAN = ["Pertanian", "Perikanan", "Perkebunan", "Peternakan", "Perdagangan", "Industri Kecil & Kerajinan", "Jasa & Pariwisata"]
AKSES_PERDAGANGAN = ["Dekat (<30 menit)", "Sedang (30-60 menit)", "Jauh (>60 menit)"]

# profil tersembunyi -> dipakai untuk membangkitkan data operasional yang realistis
TIERS = {
    "tinggi":  dict(weight=42, trans_count=(20, 35), trans_val=(400_000, 3_000_000), stok_unit=(300, 900), lapor_pct=(80, 100)),
    "sedang":  dict(weight=35, trans_count=(10, 20), trans_val=(150_000, 900_000),   stok_unit=(120, 400), lapor_pct=(50, 82)),
    "rendah":  dict(weight=23, trans_count=(0, 9),   trans_val=(50_000, 350_000),    stok_unit=(0, 150),   lapor_pct=(5, 52)),
}
TREND_OPTIONS = ["membaik", "stabil", "menurun"]
PELUANG_GONCANGAN = 0.15  # proporsi koperasi yang mengalami perubahan tier di tengah jalan


def make_desa_name():
    return f"{random.choice(DESA_PREFIX)} {random.choice(DESA_SUFFIX).capitalize()}"


def pick_tier(kecuali=None):
    tiers = [t for t in TIERS if t != kecuali]
    weights = [TIERS[t]["weight"] for t in tiers]
    return random.choices(tiers, weights=weights, k=1)[0]


def tier_pada_bulan(k, m_idx):
    """Tier efektif suatu koperasi pada bulan ke-m_idx. Sebagian kecil
    koperasi (PELUANG_GONCANGAN) mengalami "goncangan" -- tier berubah di
    tengah jalan (mis. kepengurusan baru, guncangan pasar) -- supaya data
    tidak semata mencerminkan satu profil tetap sepanjang 6 bulan. Ini
    penting untuk step 4 (model prediksi): tanpa goncangan, memprediksi
    3 bulan ke depan jadi nyaris trivial karena status tiap koperasi tidak
    pernah benar-benar berubah golongan."""
    if k["_bulan_goncang"] is not None and m_idx >= k["_bulan_goncang"]:
        return TIERS[k["_tier_goncang"]]
    return TIERS[k["_tier"]]


def trend_factor(trend, month_idx, n_months=6):
    """Mengembalikan pengali 0.6-1.3 yang menggeser data sepanjang waktu
    sesuai arah tren, supaya pola 6 bulan punya bentuk (bukan flat)."""
    progress = month_idx / (n_months - 1)  # 0..1
    if trend == "membaik":
        return 0.72 + 0.5 * progress
    if trend == "menurun":
        return 1.18 - 0.55 * progress
    return 1.0  # stabil, dengan sedikit noise ditambahkan di pemanggil


def gen_wilayah_dan_koperasi():
    wilayah_rows, koperasi_rows = [], []
    kode_w, kode_k = 1, 1
    for provinsi, kab_list in WILAYAH_SEED.items():
        for kab in kab_list:
            pmo = f"PMO-{kab.replace('Kab. ', '').replace('Kota ', '').replace(' ', '')[:10].upper()}"
            n_koperasi = max(3, TARGET_KOPERASI_PER_KABUPATEN[kab] + random.randint(-1, 1))
            for _ in range(n_koperasi):
                kode_wilayah = f"W{kode_w:04d}"
                idm_asli = ambil_desa_asli(kab)
                if idm_asli:
                    desa = idm_asli["desa"]
                    kecamatan = f"Kec. {idm_asli['kecamatan']}"
                else:
                    desa = make_desa_name()
                    kecamatan = f"Kec. {make_desa_name().split()[0]}"
                lat_pusat, lon_pusat = KABUPATEN_KOTA_COORD[kab]
                wilayah_rows.append({
                    "kode_wilayah": kode_wilayah,
                    "provinsi": provinsi,
                    "kabupaten_kota": kab,
                    "kecamatan": kecamatan,
                    "desa_kelurahan": desa,
                    "pmo_penanggung_jawab": pmo,
                    "latitude": round(lat_pusat + random.uniform(-JITTER_DERAJAT, JITTER_DERAJAT), 5),
                    "longitude": round(lon_pusat + random.uniform(-JITTER_DERAJAT, JITTER_DERAJAT), 5),
                    "_idm_asli": idm_asli,
                })

                koperasi_id = f"KDMP-{kode_k:05d}"
                tanggal_berdiri = date(2025, random.randint(7, 12), random.randint(1, 28)) \
                    if random.random() < 0.7 else date(2026, random.randint(1, 3), random.randint(1, 28))

                tier_awal = pick_tier()
                goncang = random.random() < PELUANG_GONCANGAN
                koperasi_rows.append({
                    "koperasi_id": koperasi_id,
                    "kode_wilayah": kode_wilayah,
                    "nama_koperasi": f"KDMP {desa}",
                    "tanggal_berdiri": tanggal_berdiri.isoformat(),
                    "jumlah_anggota": random.randint(45, 320),
                    "jenis_usaha": random.choice(JENIS_USAHA),
                    "status_operasional": "Aktif",
                    "_tier": tier_awal,
                    "_trend": random.choice(TREND_OPTIONS),
                    "_bulan_goncang": random.randint(2, 4) if goncang else None,
                    "_tier_goncang": pick_tier(kecuali=tier_awal) if goncang else tier_awal,
                })
                kode_w += 1
                kode_k += 1
    return wilayah_rows, koperasi_rows


def gen_profil_wilayah(wilayah_rows):
    """status_idm/skor_idm/dimensi sosial-ekonomi-lingkungan: ASLI (dari
    `_idm_asli`, hasil `prepare_idm_lookup.py`) untuk wilayah yang dapat
    jatah desa asli, SIMULASI untuk sisanya (kota berbasis kelurahan --
    lihat docstring modul). mata_pencaharian_dominan, ekonomi_beragam, dan
    akses_pusat_perdagangan TETAP simulasi untuk semua wilayah (tidak ada
    di sumber IDM) -- ekonomi_beragam & akses tetap dikorelasikan ke
    skor_idm (asli maupun simulasi) supaya konsisten secara internal."""
    rows = []
    for w in wilayah_rows:
        idm_asli = w["_idm_asli"]
        if idm_asli:
            status = idm_asli["status_idm"]
            skor_idm = float(idm_asli["skor_idm"])
            dimensi_sosial = float(idm_asli["dimensi_sosial"])
            dimensi_ekonomi = float(idm_asli["dimensi_ekonomi"])
            dimensi_lingkungan = float(idm_asli["dimensi_lingkungan"])
        else:
            status = random.choices(list(STATUS_IDM_WEIGHT.keys()), weights=list(STATUS_IDM_WEIGHT.values()), k=1)[0]
            rentang = {
                "Mandiri": (0.82, 0.95), "Maju": (0.71, 0.82), "Berkembang": (0.60, 0.71),
                "Tertinggal": (0.49, 0.60), "Sangat Tertinggal": (0.30, 0.49),
            }[status]
            skor_idm = round(random.uniform(*rentang), 3)
            jitter = lambda: round(max(0.0, min(1.0, skor_idm + random.uniform(-0.08, 0.08))), 3)
            dimensi_sosial, dimensi_ekonomi, dimensi_lingkungan = jitter(), jitter(), jitter()

        rows.append({
            "kode_wilayah": w["kode_wilayah"],
            "status_idm": status,
            "skor_idm": skor_idm,
            "dimensi_sosial": dimensi_sosial,
            "dimensi_ekonomi": dimensi_ekonomi,
            "dimensi_lingkungan": dimensi_lingkungan,
            "mata_pencaharian_dominan": random.choice(MATA_PENCAHARIAN),
            "ekonomi_beragam": random.random() < (0.25 + skor_idm * 0.6),  # desa lebih maju cenderung lebih beragam usahanya
            "akses_pusat_perdagangan": random.choices(AKSES_PERDAGANGAN, weights=[50, 35, 15], k=1)[0],
        })
    return rows


def gen_transaksi(koperasi_rows):
    rows = []
    tid = 1
    kategori_list = ["Sembako", "Simpan Pinjam", "Saprotan", "Logistik", "Lainnya"]
    for k in koperasi_rows:
        for m_idx, (ym, mdate) in enumerate(MONTHS):
            tier = tier_pada_bulan(k, m_idx)
            factor = trend_factor(k["_trend"], m_idx) * random.uniform(0.85, 1.15)
            n_trans = max(0, round(random.randint(*tier["trans_count"]) / len(MONTHS) * factor))
            for _ in range(n_trans):
                nilai = round(random.uniform(*tier["trans_val"]) * factor, -3)
                day = random.randint(1, mdate.day)
                rows.append({
                    "transaksi_id": f"TRX-{tid:07d}",
                    "koperasi_id": k["koperasi_id"],
                    "tanggal": date(mdate.year, mdate.month, day).isoformat(),
                    "jenis_transaksi": random.choice(["Penjualan", "Pembelian", "Simpan", "Pinjam"]),
                    "nilai_rupiah": nilai,
                    "kategori_produk": random.choice(kategori_list),
                })
                tid += 1
    return rows


def gen_stok(koperasi_rows):
    rows = []
    sid = 1
    barang_list = ["Beras", "Minyak Goreng", "Pupuk", "Gula", "Sembako Campuran"]
    for k in koperasi_rows:
        for m_idx, (ym, mdate) in enumerate(MONTHS):
            tier = tier_pada_bulan(k, m_idx)
            factor = trend_factor(k["_trend"], m_idx) * random.uniform(0.9, 1.1)
            unit = max(0, round(random.uniform(*tier["stok_unit"]) * factor))
            nilai = round(unit * random.uniform(8_000, 25_000), -3)
            rows.append({
                "stok_id": f"STK-{sid:06d}",
                "koperasi_id": k["koperasi_id"],
                "tanggal_pencatatan": mdate.isoformat(),
                "jenis_barang": random.choice(barang_list),
                "jumlah_unit": unit,
                "nilai_rupiah": nilai,
            })
            sid += 1
    return rows


def gen_laporan(koperasi_rows):
    rows = []
    lid = 1
    for k in koperasi_rows:
        for m_idx, (ym, mdate) in enumerate(MONTHS):
            tier = tier_pada_bulan(k, m_idx)
            factor = trend_factor(k["_trend"], m_idx)
            lo, hi = tier["lapor_pct"]
            pct = max(0, min(100, round(random.uniform(lo, hi) * min(factor, 1.15), 1)))
            submit_day = min(mdate.day, random.randint(1, 10))
            rows.append({
                "laporan_id": f"LAP-{lid:06d}",
                "koperasi_id": k["koperasi_id"],
                "periode": ym,
                "tanggal_submit": date(mdate.year, mdate.month, submit_day).isoformat(),
                "persen_kelengkapan": pct,
            })
            lid += 1
    return rows


def strip_internal(rows):
    """Buang field _tier/_trend sebelum ditulis -- bukan bagian skema resmi."""
    return [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]


def write_csv(rows, name):
    if not rows:
        return
    path = os.path.join(OUTPUT_DIR, f"{name}.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_sqlite(tables):
    db_path = os.path.join(OUTPUT_DIR, "sigap_kopdes.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    for name, rows in tables.items():
        if not rows:
            continue
        cols = list(rows[0].keys())
        col_defs = ", ".join(f'"{c}" TEXT' for c in cols)
        cur.execute(f'CREATE TABLE "{name}" ({col_defs})')
        placeholders = ", ".join(["?"] * len(cols))
        cur.executemany(
            f'INSERT INTO "{name}" VALUES ({placeholders})',
            [[r[c] for c in cols] for r in rows],
        )
    conn.commit()
    conn.close()
    return db_path


def main():
    wilayah_rows_full, koperasi_rows_full = gen_wilayah_dan_koperasi()
    profil_wilayah_rows = gen_profil_wilayah(wilayah_rows_full)
    transaksi_rows = gen_transaksi(koperasi_rows_full)
    stok_rows = gen_stok(koperasi_rows_full)
    laporan_rows = gen_laporan(koperasi_rows_full)
    koperasi_rows = strip_internal(koperasi_rows_full)
    wilayah_rows = strip_internal(wilayah_rows_full)

    tables = {
        "wilayah": wilayah_rows,
        "profil_wilayah": profil_wilayah_rows,
        "koperasi": koperasi_rows,
        "transaksi": transaksi_rows,
        "stok": stok_rows,
        "laporan": laporan_rows,
    }
    for name, rows in tables.items():
        write_csv(rows, name)
    db_path = write_sqlite(tables)

    n_asli = sum(1 for w in wilayah_rows_full if w["_idm_asli"])
    print(f"Selesai. {len(koperasi_rows)} koperasi dibangkitkan di {len(wilayah_rows)} wilayah.")
    print(f"  - profil IDM ASLI (data 2024, Kemendes PDTT): {n_asli} wilayah")
    print(f"  - profil IDM simulasi (kota berbasis kelurahan, di luar cakupan IDM): {len(wilayah_rows) - n_asli} wilayah")
    print(f"  - transaksi : {len(transaksi_rows)} baris")
    print(f"  - stok      : {len(stok_rows)} baris")
    print(f"  - laporan   : {len(laporan_rows)} baris")
    print(f"SQLite ditulis ke: {db_path}")
    print(f"CSV per tabel di : {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
