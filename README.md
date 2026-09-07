# SIGAP Kopdes

Sistem Deteksi Dini Kesehatan Usaha Koperasi Desa/Kelurahan Merah Putih (KDMP) — dibuat untuk LAN Datathon 2026 (subtema Koperasi dan Pemberdayaan Ekonomi Masyarakat).

Dokumen lengkap: lihat `Proposal_SIGAP_Kopdes_LAN_Datathon_2026.docx`.

## Roadmap pengerjaan

- [x] **1. Struktur proyek & rencana teknis** — folder ini
- [x] **2. Data layer** — generator data simulasi sesuai skema (`backend/data/generate_data.py`)
- [x] **3. Engine skor kesehatan** — hitung skor komposit dari data mentah (`backend/scoring/compute_scores.py`)
- [x] **4. Model prediksi risiko** — proyeksi risiko kritis 3 bulan ke depan (`backend/prediction/predict_risk.py`)
- [x] **5. AI Insight & Rekomendasi** — LLM menarasikan kondisi + saran tindakan per koperasi, dibangun di atas step 3 & 4 (`backend/ai_insight/generate_insight.py`)
- [x] **6. Backend API** — FastAPI yang menyajikan skor, prediksi, dan insight AI (`backend/api/main.py`)
- [x] **7. Dashboard React** — terhubung langsung ke API step 6 (`frontend/`); tidak ada mockup lama untuk dihubungkan, dibangun dari nol (lihat catatan di bawah)
- [x] **Autentikasi & Otorisasi** — ditambahkan sebelum deployment karena data ini sensitif (`backend/auth/`); login wajib, akses PMO dibatasi per wilayah
- [ ] **8. Deployment** — backend + frontend online agar bisa diakses juri

Kita kerjakan satu per satu — centang bertambah tiap step selesai.

> **Kenapa step 5 ditaruh setelah 3 & 4, bukan lebih awal?** Modul insight AI menarasikan skor (step 3) dan proyeksi risiko (step 4) yang SUDAH dihitung — LLM diberi angka jadi, tugasnya menjelaskan dan menyarankan tindakan, bukan menghitung sendiri. Ini penting supaya angka yang tampil di dashboard tetap bisa dipertanggungjawabkan (bukan hasil karangan model bahasa).

## Struktur folder

```
sigap-kopdes/
├── README.md
├── backend/
│   ├── requirements.txt
│   ├── data/
│   │   ├── generate_data.py       # step 2
│   │   ├── prepare_idm_lookup.py  # sekali-jalan: saring data IDM asli (lihat bagian step 2)
│   │   ├── idm_2024_lookup.csv    # hasil saringan, dibaca generate_data.py
│   │   └── output/                # sigap_kopdes.db + csv (hasil generate)
│   ├── scoring/
│   │   └── compute_scores.py      # step 3
│   ├── prediction/
│   │   └── predict_risk.py        # step 4
│   ├── ai_insight/
│   │   └── generate_insight.py    # step 5
│   ├── api/
│   │   └── main.py                # step 6
│   └── auth/
│       ├── auth.py                # login, JWT, scope wilayah
│       ├── create_user.py         # CLI bikin akun (tidak ada registrasi mandiri)
│       └── auth.db                # users -- TERPISAH dari sigap_kopdes.db, lihat bagian Autentikasi
├── frontend/                      # step 7: dashboard React (Vite) -- role admin & pmo, lihat src/
└── frontend-admin/                # portal superadmin (React/Vite) TERPISAH -- manajemen akun,
                                    # lihat bagian "Portal Superadmin (Manajemen Akun)"
```

## Kalau baru pertama kali baca kode ini (pakai Claude Code)

Urutan baca yang disarankan, dari fondasi ke lapisan paling atas — tiap file dibangun di atas file sebelumnya:

1. `backend/data/generate_data.py` — struktur data & cara data disimulasikan, termasuk catatan soal "goncangan" tier (kenapa itu ditambahkan belakangan, lihat docstring)
2. `backend/scoring/compute_scores.py` — cara skor kesehatan dihitung dari data mentah. Docstring-nya cerita soal bug metodologi persentil yang sempat salah
3. `backend/prediction/predict_risk.py` — model prediksi risiko. Docstring-nya cerita soal ROC-AUC yang sempat mencurigakan (0.99) dan kenapa itu tanda bahaya, bukan prestasi
4. `backend/ai_insight/generate_insight.py` — lapisan AI paling atas, mengonsumsi hasil dari 3 file di atas. Baca `PROMPT_TEMPLATE` untuk lihat persis apa yang dikirim ke LLM
5. `backend/api/main.py` — lapisan API (step 6), murni query/join dari `sigap_kopdes.db`, tidak menghitung apa pun sendiri
6. `frontend/src/` — dashboard React (step 7), sudah terhubung ke API asli sejak awal (bukan data dummy) — mulai dari `App.jsx` (routing) lalu `pages/`

Tiap file punya docstring yang jelaskan bukan cuma APA yang dikerjakan tapi KENAPA — termasuk 2 bug nyata yang sempat ditemukan lalu diperbaiki. Baca docstring-nya dulu sebelum baca kode baris per baris; itu jalan pintas paling efisien untuk paham keputusan desainnya.

Prompt awal yang bisa dicoba begitu sesi Claude Code terbuka di folder ini: *"Baca README.md ini, lalu jelaskan alur data dari generate_data.py sampai generate_insight.py, dan sebutkan 2 bug yang pernah ditemukan di project ini."*

## Menjalankan step 2 (data simulasi)

```bash
cd backend
pip install -r requirements.txt   # belum ada dependency eksternal di step ini
python data/generate_data.py
```

Output: `backend/data/output/sigap_kopdes.db` (SQLite, 6 tabel sesuai skema termasuk `profil_wilayah`) dan file `.csv` per tabel untuk inspeksi cepat.

Data operasional (TRANSAKSI/STOK/LAPORAN/KOPERASI) **tetap simulasi 100%** (bukan data KDMP asli) — KDMP sungguhan belum eksis di dataset ini, sesuai yang tertulis di proposal. `wilayah` juga menyimpan `latitude`/`longitude` (titik pusat kabupaten/kota ASLI + sebaran acak kecil per desa) untuk halaman Peta di step 7 — provinsi & kabupaten/kota di `WILAYAH_SEED` memang nama wilayah Indonesia sungguhan, hanya desa/kelurahan fiktif untuk sebagian wilayah (lihat di bawah).

**`profil_wilayah` SEBAGIAN memakai data ASLI**, bukan simulasi penuh lagi. Ada file Excel resmi *Indeks Desa Membangun (IDM) 2024 hasil pemutakhiran* (Kemendes PDTT) yang bisa disaring lewat:

```bash
cd backend/data
pip install openpyxl   # cuma dipakai sekali di sini, tidak masuk requirements.txt
python prepare_idm_lookup.py "/path/ke/indeks-desa-membangun-2024....xlsx"
```

Ini menghasilkan `idm_2024_lookup.csv` (sudah ada di repo, jadi langkah ini opsional kecuali Anda ganti/perbarui file sumbernya) yang dibaca `generate_data.py` setiap kali dijalankan. Untuk **13 dari 21** kabupaten/kota di `WILAYAH_SEED` yang berstatus "Kabupaten", nama desa + `dimensi_sosial`/`dimensi_ekonomi`/`dimensi_lingkungan` + `status_idm`/`skor_idm` di `profil_wilayah` sekarang ASLI dari IDM 2024 (2.822 desa tersaring, jauh lebih banyak dari yang dibutuhkan). **8 kabupaten/kota sisanya berstatus "Kota" tetap simulasi penuh** — bukan keterbatasan yang disembunyikan, tapi cerminan struktur pemerintahan asli: IDM secara definisi hanya mencakup DESA (kewenangan Kemendes PDTT), bukan KELURAHAN (wilayah kota, kewenangan Kemendagri), jadi kota-kota itu memang tidak punya data IDM untuk diambil. `mata_pencaharian_dominan`, `ekonomi_beragam`, `akses_pusat_perdagangan` tetap simulasi untuk SEMUA wilayah (tidak ada di sumber IDM).

Catatan jujur soal usia data: IDM 2024 adalah data **per 2024**, bukan data berjalan/real-time — disebutkan apa adanya kalau ditanya juri, bukan diklaim sebagai kondisi terkini.

**Kalau database lama Anda dibuat sebelum perubahan lat/lon & IDM asli ini:** jalankan ulang `generate_data.py` lalu `compute_scores.py` dan `predict_risk.py` (step 3 & 4) supaya skema `wilayah`/`profil_wilayah` ter-update dan skor/prediksi konsisten dengan data baru — `generate_data.py` menghapus & menulis ulang seluruh `sigap_kopdes.db` tiap dijalankan (lihat `write_sqlite()`), jadi tabel `skor_kesehatan`/`notifikasi`/`ai_insight` ikut hilang dan perlu dihitung ulang (tabel `users` di `auth.db` AMAN, disimpan terpisah -- lihat bagian Autentikasi).

## Menjalankan step 3 (engine skor kesehatan)

```bash
cd backend
python scoring/compute_scores.py   # butuh pandas: pip install pandas
```

Membaca tabel mentah dari `sigap_kopdes.db`, menghitung skor 0-100 per koperasi per bulan (metodologi lengkap ada di docstring `compute_scores.py`), lalu menulis tabel `skor_kesehatan` dan `notifikasi` ke database + CSV yang sama.

**Parameter yang bisa disetel** (di bagian atas file): bobot tiap komponen skor (`BOBOT`), ambang kategori (`BATAS_SEHAT`, `BATAS_WASPADA`), dan ambang notifikasi penurunan skor (`TURUN_SIGNIFIKAN`) — saat ini pakai rata-rata sederhana sebagai baseline yang bisa disesuaikan nanti.

## Menjalankan step 4 (model prediksi risiko)

```bash
cd backend
python prediction/predict_risk.py   # butuh scikit-learn, joblib
```

Melatih regresi logistik dari histori skor (fitur: skor komposit + 3 sub-skor + tren 1 & 2 bulan terakhir) untuk memprediksi probabilitas sebuah koperasi jatuh ke kategori Kritis 3 bulan ke depan, lalu mengisi kolom `prediksi_risiko_3bln` di tabel `skor_kesehatan`.

Catatan jujur: percobaan pertama menghasilkan ROC-AUC 0.99 yang **terlalu bagus untuk dipercaya** — ternyata karena `generate_data.py` awalnya memberi tiap koperasi satu profil kesehatan tetap sepanjang 6 bulan, jadi "memprediksi masa depan" jadi nyaris trivial. Sudah diperbaiki: `generate_data.py` sekarang memberi ~15% koperasi "goncangan" (perubahan tier di tengah jalan) supaya data lebih realistis. Setelah perbaikan, ROC-AUC turun ke ~0.87 — lebih rendah, tapi jauh lebih bisa dipertanggungjawabkan kalau ditanya juri.

## Menjalankan step 5 (AI Insight & Rekomendasi)

Dua provider LLM didukung, dipilih lewat env var `AI_PROVIDER` (default `anthropic`) — `PROMPT_TEMPLATE` dan skema JSON keluarannya **sama persis** untuk keduanya, cuma cara memanggil API-nya yang beda:

```bash
cd backend
pip install -r requirements.txt   # perlu paket anthropic (default)

# 1. Cek dulu prompt & alur datanya TANPA memanggil API (gratis, provider apa pun):
python ai_insight/generate_insight.py --dry-run --koperasi KDMP-00001

# 2a. Pakai Claude (default) -- perlu API key berbayar:
export ANTHROPIC_API_KEY=sk-ant-...
python ai_insight/generate_insight.py --koperasi KDMP-00001   # satu koperasi
python ai_insight/generate_insight.py                          # semua koperasi, periode terbaru

# 2b. ATAU pakai Gemini Flash -- GRATIS, tanpa kartu kredit untuk tier gratis:
pip install google-genai   # butuh Python >= 3.10 (cek: python3 --version)
export AI_PROVIDER=gemini
export GEMINI_API_KEY=...   # bikin di https://aistudio.google.com/apikey
python ai_insight/generate_insight.py --koperasi KDMP-00001
```

**Kalau `python3` sistem Anda lebih lama dari 3.10** (paket `google-genai` menolak versi di bawah itu): sama seperti kasus Node.js di step 7, cek dulu apakah ada Python versi lebih baru sudah terpasang (`ls /usr/local/Cellar/python*` di Homebrew macOS, atau `pyenv versions`) sebelum install versi baru — pakai `python3.12 -m venv .venv && source .venv/bin/activate` supaya tidak menimpa `python3` default sistem.

Kuota & syarat tier gratis Gemini bisa berubah — cek angka terkini di [ai.google.dev/gemini-api/docs/rate-limits](https://ai.google.dev/gemini-api/docs/rate-limits) sebelum mengandalkannya untuk volume besar. Model yang dipakai (`GEMINI_MODEL` di `generate_insight.py`) juga bisa perlu di-update seiring waktu kalau Google mengganti nama model tier gratisnya.

**Bug ke-4 yang ditemukan (saat menguji integrasi Gemini dengan API key sungguhan):** `simpan()` awalnya pakai `df.to_sql("ai_insight", conn, if_exists="replace", index=False)` polos -- niatnya "tulis ulang tabel dengan hasil run ini", tapi konsekuensinya menjalankan `--koperasi X` (dirancang untuk regenerasi SATU koperasi saja) diam-diam **menghapus insight semua koperasi lain** yang sudah pernah dibuat, karena seluruh tabel ditimpa cuma dengan baris dari run itu. Ketahuan persis saat generate 2 koperasi berturut-turut dengan Gemini -- koperasi pertama hilang setelah koperasi kedua diproses. Diperbaiki jadi UPSERT per `(koperasi_id, periode)`: baca tabel lama, buang baris yang kunci-nya sama dengan hasil run ini, gabung dengan hasil baru, baru ditulis ulang -- sudah diverifikasi baris lain tetap ada & tidak terduplikasi saat koperasi yang sama diproses ulang.

### Generate ON-DEMAND lewat dashboard (bukan cuma batch CLI)

Cara di atas (CLI, `--koperasi`/batch semua) tetap ada, tapi **bukan satu-satunya jalan lagi**. `backend/api/main.py` sekarang generate insight **realtime** begitu dashboard membuka halaman detail koperasi yang belum pernah punya insight tersimpan -- klik koperasi di Daftar Koperasi, endpoint `GET /insight/{koperasi_id}` cek cache dulu, kalau kosong baru panggil LLM saat itu juga (~2-15 detik tergantung provider), simpan hasilnya, lalu kunjungan berikutnya ke koperasi yang sama langsung dari cache (tanpa panggil LLM lagi). Ini dipilih supaya **kuota API cuma terpakai untuk koperasi yang benar-benar dilihat pengguna**, bukan di-generate sekaligus untuk semua koperasi (banyak di antaranya mungkin tidak pernah dibuka siapa pun).

Konsekuensinya: **backend API (step 6) butuh API key provider yang sama** seperti CLI (`ANTHROPIC_API_KEY` atau `GEMINI_API_KEY` + `AI_PROVIDER=gemini`) di environment-nya saat dijalankan (lihat `uvicorn api.main:app`) -- kalau belum di-set, endpoint balas `503` dengan pesan jelas (bukan error 500 misterius), dan frontend menampilkan pesan yang sama ke pengguna alih-alih AI insight-nya.

Di frontend, kartu AI Insight (`src/components/AiInsightCard.jsx`) menampilkan **skeleton shimmer + indikator "sedang berpikir"** selagi generate berlangsung, lalu tiap kartu hasil muncul dengan animasi fade-in bertahap (bukan cuma kartu yang sudah di-cache -- itu tampil langsung tanpa animasi supaya tidak berkedip tiap kali halaman dibuka ulang). Menghormati `prefers-reduced-motion`.

**Bug ke-5 yang ditemukan (saat kuota gratis Gemini beneran habis di pengujian):** pesan error 502 sempat tampil **dobel** ("Gagal membuat AI insight: Gagal membuat AI insight: Error code 429...") plus dump JSON mentah dari provider -- ternyata backend DAN frontend sama-sama menambahkan prefix "Gagal membuat AI insight:" ke pesan yang sama. Diperbaiki dengan `ringkas_error_llm()` di `api/main.py`: backend sekarang mengenali pola kuota/rate-limit dan mengembalikan SATU kalimat Indonesia yang jelas & actionable ("Kuota API provider LLM untuk hari ini sudah habis... coba lagi nanti, atau ganti AI_PROVIDER"), frontend cuma menampilkannya apa adanya tanpa prefix tambahan.

Menghasilkan 5 hal per koperasi (disimpan ke tabel `ai_insight`):
- `narasi` — kondisi koperasi, dari skor & tren (step 3-4)
- `rekomendasi_tindakan` — satu aksi diagnostik konkret untuk PMO
- `produk_prioritas` — **array** 2-3 ide produk/jasa, dari mata pencaharian dominan & keragaman ekonomi wilayah (`profil_wilayah`)
- `rekomendasi_promosi` — satu ide kampanye/promosi konkret + momentum waktunya
- `rekomendasi_program` — **array** 2-3 ide program non-produk (pelatihan, kemitraan, digitalisasi, dst.), ditarik dari dimensi sosial/ekonomi/lingkungan & akses pasar wilayah

`produk_prioritas` & `rekomendasi_program` disimpan sebagai JSON array di kolom TEXT (SQLite tidak punya tipe list) — diurai balik jadi array asli oleh backend API (step 6) sebelum dikirim ke frontend.

**Soal "data eksternal" (mis. IDM) untuk rekomendasi:** `profil_wilayah` (step 2) SUDAH mensimulasikan struktur IDM lengkap sejak awal (status, skor, dimensi sosial/ekonomi/lingkungan, keragaman ekonomi, akses pasar) — sebelumnya cuma `mata_pencaharian_dominan` & `status_idm` yang dipakai di prompt, sekarang seluruh field itu dikirim ke LLM sebagai basis `produk_prioritas`/`rekomendasi_promosi`/`rekomendasi_program`. Project ini tidak mengintegrasikan API IDM/pemerintah sungguhan — seluruh dataset memang simulasi (lihat docstring `generate_data.py`), jadi "data eksternal" di sini berhenti di simulasi yang sudah ada, bukan panggilan API baru.

**Prinsip desain (ditegakkan di kode, bukan cuma di proposal):** prompt HANYA berisi angka yang sudah dihitung `compute_scores.py`, `predict_risk.py`, dan profil wilayah dari `generate_data.py` — LLM diinstruksikan eksplisit untuk tidak menghitung ulang atau mengarang data wilayah baru, cuma menarasikan & menyarankan. Ini berlaku sama untuk provider mana pun (Claude atau Gemini) karena keduanya menerima `PROMPT_TEMPLATE` yang identik. Sudah diuji jalur datanya (join skor + koperasi + wilayah + profil_wilayah) lewat `--dry-run`; pemanggilan API sungguhan perlu API key milik Anda sendiri (Anthropic atau Google, tergantung `AI_PROVIDER`) — sandbox saya tidak menyimpan API key siapa pun.

## Menjalankan step 6 (Backend API)

```bash
cd backend
pip install -r requirements.txt   # perlu fastapi, uvicorn
uvicorn api.main:app --reload --port 8000
```

Dokumentasi interaktif (Swagger UI): http://localhost:8000/docs

Endpoint utama:

| Endpoint | Kegunaan |
|---|---|
| `GET /koperasi` | Daftar koperasi + skor, prediksi, lat/lon (filter: `kategori`, `kode_wilayah`, `kabupaten_kota`, `provinsi`, `periode`) |
| `GET /koperasi/{koperasi_id}` | Detail 1 koperasi: profil, histori skor semua periode, AI insight terbaru |
| `GET /skor` | Baris `skor_kesehatan` mentah (filter: `periode`, `koperasi_id`) |
| `GET /notifikasi` | Notifikasi otomatis dari step 3 (filter: `status_tindak_lanjut`, `koperasi_id`) |
| `GET /insight/{koperasi_id}` | AI insight -- dari cache kalau sudah ada, ATAU generate on-demand saat itu juga kalau belum (lihat bagian "Generate ON-DEMAND" di step 5). 503 kalau server belum ada API key provider, 502 kalau panggilan LLM gagal |
| `GET /wilayah` | Daftar wilayah + profil IDM gabungan |
| `GET /ringkasan` | Agregat untuk kartu dashboard (jumlah per kategori, rata-rata skor, notifikasi belum ditindaklanjuti) |
| `GET /peta/provinsi` | Agregat kesehatan per provinsi (level 1 peta) — jumlah koperasi, rata-rata skor, kategori agregat, koordinat |
| `GET /peta/kabupaten?provinsi=...` | Agregat kesehatan per kabupaten/kota DALAM satu provinsi (level 2 peta) |
| `GET /metodologi` | Ambang & bobot skor (`BATAS_SEHAT`, `BATAS_WASPADA`, `BOBOT`, `TURUN_SIGNIFIKAN`, `GAP_BULAN_PREDIKSI`) untuk halaman "Kriteria & Metodologi" -- diambil langsung dari `compute_scores.py`/`predict_risk.py`, bukan diketik ulang |

Kategori agregat di `/peta/*` dihitung dari skor RATA-RATA wilayah dengan ambang yang sama seperti skor individual (`BATAS_SEHAT`/`BATAS_WASPADA`, di-*import* langsung dari `scoring/compute_scores.py` supaya tidak ada dua sumber kebenaran ambang) — bukan berarti semua koperasi di wilayah itu senyatanya berkategori sama, cuma penyederhanaan untuk tampilan agregat.

**Prinsip desain (konsisten dengan step 3-5):** API ini murni membaca & menyusun ulang (query, join) data dari `sigap_kopdes.db` — tidak menghitung skor/prediksi/insight sendiri. Endpoint `/insight/*` menoleransi tabel `ai_insight` yang belum ada (mengembalikan 404 yang jelas, bukan error 500) karena tabel itu baru terisi setelah step 5 dijalankan sungguhan dengan `ANTHROPIC_API_KEY` milik Anda sendiri.

**Semua endpoint di atas (kecuali `/`) sekarang butuh login** — lihat bagian "Autentikasi & Otorisasi" di bawah. `CORS_ORIGINS` juga tidak lagi wildcard `"*"`, default ke `http://localhost:5173` (bisa diubah lewat environment variable, dipisah koma untuk lebih dari satu origin).

## Menjalankan step 7 (Dashboard React)

Catatan: `mockup_dashboard_sigap_kopdes.jsx` yang tadinya direncanakan sebagai basis step 7 **tidak pernah ada di project ini** -- dashboard di `frontend/` dibangun dari nol, langsung terhubung ke API step 6 (bukan data dummy yang diganti belakangan).

```bash
cd frontend
npm install
cp .env.example .env   # sesuaikan VITE_API_BASE_URL kalau API tidak di localhost:8000
npm run dev
```

Buka http://localhost:5173 — pastikan backend API (step 6) sudah jalan di port 8000 lebih dulu. Anda akan diarahkan ke `/login` dulu (lihat bagian Autentikasi) sebelum bisa lihat dashboard apa pun.

Halaman yang ada: **Ringkasan** (stat tile jumlah per kategori + notifikasi tertunda, dan **Peta Sebaran Koperasi** sebagai bagian dari halaman ini — bukan halaman terpisah, lihat catatan di bawah), **Daftar Koperasi** (tabel dengan filter kategori/wilayah), **Detail Koperasi** (profil + tren skor 4-seri + kartu AI insight 5-bagian, di-generate ON-DEMAND realtime saat pertama kali dibuka -- `src/components/AiInsightCard.jsx` -- lihat "Generate ON-DEMAND" di step 5), **Notifikasi** (filter status, diambil dinamis dari data -- lihat catatan bug di bawah), **Kriteria & Metodologi** (penjelasan lengkap kategori Sehat/Waspada/Kritis, cara hitung skor komposit, arti proyeksi risiko, dan status IDM — dengan tooltip ikon "ⓘ" di titik-titik terkait pada halaman lain, `src/components/InfoTooltip.jsx`).

**Peta (bagian dari Ringkasan, komponen `src/components/PetaWilayah.jsx`):** klik lingkaran provinsi → zoom & tampilkan lingkaran per kabupaten/kota di provinsi itu → klik lagi → tampilkan marker tiap koperasi (warna = kategori skor terbaru), klik marker koperasi untuk buka halaman detailnya. Ukuran lingkaran agregat sebanding jumlah koperasi (skala akar kuadrat), warnanya dari kategori agregat (`/peta/provinsi`, `/peta/kabupaten`). Butuh akses internet saat runtime untuk memuat tile OpenStreetMap (`{s}.tile.openstreetmap.org`) — sertakan atribusi OSM yang sudah ada di pojok kanan-bawah peta kalau dipakai publik. Warna status di peta pakai hex tetap (`src/statusColors.js`), tidak ikut tema gelap/terang, karena tile peta selalu berlatar terang. Untuk akun `pmo`, peta & seluruh isi Ringkasan otomatis terbatas ke wilayah scope-nya (difilter di backend, bukan disembunyikan di frontend).

**Kalau Node.js sistem Anda lebih lama dari 20/22** (tooling Vite/`create-vite` terbaru butuh itu): project ini divalidasi jalan dengan Node 21.4 yang di-install via Homebrew tapi belum di-`brew link` (supaya tidak menimpa Node lain yang sudah ada di `/usr/local/bin`) — jalankan dengan menambahkan `PATH` sementara, contoh:
```bash
export PATH="$(brew --prefix node)/libexec/bin:$(brew --prefix node)/bin:$PATH"
```

**Bug ke-3 yang ditemukan (di luar 2 bug pipeline step 2-4):** endpoint `/ringkasan` dan filter Notifikasi awalnya diasumsikan pakai status `"Belum"`/`"Sudah"` untuk `status_tindak_lanjut` -- ternyata `compute_scores.py` cuma pernah menulis `"Baru"` untuk semua notifikasi (belum ada alur di sistem manapun yang mengubahnya). Akibatnya kartu "notifikasi belum ditindaklanjuti" di dashboard sempat selalu menunjukkan 0 walau ada 424 notifikasi. Diperbaiki dengan mengecek nilai asli di database dulu, lalu (a) ganti filter di `backend/api/main.py` ke `"Baru"`, dan (b) di frontend, dropdown filter Notifikasi diambil dinamis dari data yang ada (bukan di-hardcode) supaya tidak salah asumsi lagi kalau nilainya berubah nanti.

## Autentikasi & Otorisasi

**Kenapa ini ditambahkan (bukan cuma prinsip abstrak):** sebelum bagian ini ada, dashboard 100% read-only tanpa input pengguna sama sekali (jadi risiko *injection* dari sisi user memang nyaris nol -- semua query API sudah parameterized sejak step 6), TAPI juga tanpa proteksi akses apa pun. `CORS_ORIGINS` dulunya wildcard `"*"` dan semua endpoint terbuka bebas. Begitu step 8 mem-publikasikan API ini ke internet, itu berarti siapa pun yang tahu URL-nya bisa melihat kondisi finansial setiap koperasi di semua wilayah -- data yang secara alami sensitif. Ini bukan cuma soal "secure by design" secara prinsip, tapi celah nyata yang harus ditutup sebelum step 8.

**Bagaimana data masuk ke sistem (konteks penting):** dashboard ini TETAP murni read-only -- tidak ada form input, tidak ada endpoint `POST`/`PUT`/`DELETE` untuk data koperasi. Yang ditambahkan di sini HANYA lapisan akses (siapa boleh MELIHAT apa), bukan alur input data baru.

### Desain

- **Tabel `users` di `auth.db`, TERPISAH dari `sigap_kopdes.db`** -- supaya akun tidak ikut terhapus tiap kali `generate_data.py` menulis ulang total database data (lihat `write_sqlite()`).
- **Password di-hash dengan bcrypt**, tidak pernah disimpan/di-log plain text.
- **Sesi berbasis JWT** (stateless), berlaku 8 jam, payload berisi `username`, `role`, dan `scope` wilayah.
- **Tiga role:**
  - `admin` -- akses semua wilayah data koperasi (Ringkasan/Daftar Koperasi/dst di `frontend/`), tanpa filter. TIDAK bisa membuat/menghapus akun atau reset password orang lain. Akun peran ini yang dipegang **Pemerintah Pusat** -- ditampilkan sebagai "Pemerintah Pusat (Admin)" di UI (`frontend/src/App.jsx`, `frontend-admin/src/pages/UsersPage.jsx`), walau nilai `role` di database tetap `admin` (cuma label tampilan yang diubah, bukan identifier internal -- lebih aman & lebih sedikit yang perlu diubah daripada rename kolom/CHECK constraint).
  - `pmo` -- dibatasi ke daftar `kode_wilayah` di kolom `kode_wilayah_scope`. Filter diterapkan **di lapisan SQL** (`WHERE kode_wilayah IN (...)`, lihat `scope_clause()` di `auth/auth.py`), bukan disaring belakangan di Python -- data di luar scope tidak pernah keluar dari database sama sekali. PMO tanpa scope (kosong) sengaja **fail closed** (tidak lihat apa pun), bukan fail open (default lihat semua).
  - `superadmin` -- **kebalikan dari admin**: HANYA bisa mengelola akun & API key AI Insight (lewat `frontend-admin/`, portal terpisah -- lihat bagian "Portal Superadmin" di bawah), dan sengaja TIDAK BISA lihat data koperasi sama sekali (bukan `is_admin`, scope-nya selalu kosong, jadi `scope_clause()` fail closed di semua endpoint data). Dipisah dari role `admin` supaya kalau `admin` dipakai lebih dari satu orang (mis. beberapa staf Pemerintah Pusat) untuk kebutuhan lihat-data, mereka tidak otomatis punya wewenang bikin/hapus login orang lain. **Cuma boleh ada SATU superadmin, selamanya** -- endpoint `/admin/users` (POST/PUT) menolak `role=superadmin` sama sekali (bukan cuma "kalau sudah ada satu"), supaya superadmin yang sedang login tidak bisa membuat superadmin lain lewat portalnya sendiri (privilege escalation). Satu-satunya jalan untuk (mengganti) superadmin adalah CLI `create_user.py --role superadmin`, yang juga menolak kalau sudah ada superadmin lain dengan username berbeda -- lihat kode di `auth/create_user.py`.
  - Koperasi/insight di luar scope PMO dikembalikan sebagai 404 (bukan 403) -- supaya tidak membocorkan ke PMO bahwa suatu `koperasi_id` sebenarnya ada di wilayah lain.
- **Wajib ganti password saat login pertama** (`must_change_password`) -- akun baru (lewat CLI atau portal superadmin) dan akun yang di-reset passwordnya SELALU dibuat dengan flag ini menyala, karena password awalnya diketahui admin/superadmin, bukan rahasia milik pemiliknya. Dicek **fresh dari `auth.db` tiap request** (`get_active_user` di `auth/auth.py`), bukan dari isi token JWT -- supaya reset password paksa atau hapus akun oleh superadmin langsung berlaku di request berikutnya, tanpa menunggu token lama (8 jam) kedaluwarsa.
- **Tidak ada halaman registrasi mandiri** -- ini alat internal, bukan aplikasi publik. Akun dibuat lewat CLI (paling awal, buat akun superadmin pertama) atau lewat portal superadmin sesudahnya:

```bash
cd backend
export JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")   # WAJIB, lihat di bawah
export CORS_ORIGINS=http://localhost:5173,http://localhost:5174,http://admin.localhost:5174   # lihat "Portal Superadmin"

# Akun superadmin pertama (WAJIB dibuat lewat CLI -- tidak ada superadmin
# lain yang bisa membuatnya lewat UI sebelum ini ada):
python auth/create_user.py --username superadmin --role superadmin

# Akun admin (akses semua wilayah DATA koperasi, bukan manajemen akun):
python auth/create_user.py --username admin --role admin

# Akun PMO dibatasi satu kabupaten/kota (resolve otomatis semua
# kode_wilayah di kabupaten itu dari sigap_kopdes.db):
python auth/create_user.py --username pmo_bandung --role pmo --kabupaten "Kab. Bandung"
```

Password diminta lewat prompt tersembunyi (tidak lewat argumen command line, supaya tidak bocor ke shell history). Menjalankan ulang dengan `--username` yang sama meng-UPSERT (ganti password/scope), bukan menduplikasi akun -- dan (sama seperti reset lewat portal superadmin) selalu menyalakan lagi `must_change_password`.

### `JWT_SECRET` WAJIB di-set

API **menolak start** kalau `JWT_SECRET` kosong -- sengaja tidak ada default tertanam di kode (secret hardcoded adalah salah satu penyebab kebocoran paling umum). Generate sekali lalu simpan di environment (`.env` lokal, secret manager kalau di step 8 nanti) -- **jangan pernah commit nilai ini ke git**:

```bash
export JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
```

### Menjalankan dengan auth aktif

```bash
cd backend
export JWT_SECRET=...   # dari atas
export CORS_ORIGINS=http://localhost:5173,http://localhost:5174,http://admin.localhost:5174
uvicorn api.main:app --reload --port 8000
```

Login lewat `POST /auth/login` (body JSON `{"username", "password"}`) mengembalikan `{access_token, token_type, role, scope, must_change_password}`. Sertakan `Authorization: Bearer <access_token>` di semua request endpoint lain -- `frontend/src/api.js` & `AuthContext.jsx` (dan versi ringkasnya di `frontend-admin/src/api.js` & `App.jsx`) sudah menangani ini otomatis (token disimpan, dipasang ke tiap request, auto-logout kalau server balas 401, dan redirect ke halaman ganti password kalau `must_change_password` true atau server balas 403 `MUST_CHANGE_PASSWORD`).

### Portal Superadmin (Manajemen Akun) -- `frontend-admin/`

Manajemen akun (buat/edit/reset password/hapus) SENGAJA **bukan** halaman di dalam dashboard utama (`frontend/`) -- ini app React **terpisah**, dengan build & deployment sendiri, supaya bisa ditaruh di subdomain lain yang tidak publik/tidak ditautkan dari mana pun (mis. `admin.domain-anda.com` di produksi, vs `domain-anda.com` untuk dashboard biasa). Login di portal ini menolak akun yang bukan `superadmin`, dan sebaliknya login dashboard utama menolak akun `superadmin` -- dua arah, ditegakkan di frontend (pesan jelas) **dan** backend (`get_superadmin_user`/`get_active_user`, endpoint `/admin/*` benar-benar 403 kalau bukan superadmin, bukan cuma disembunyikan di UI).

Role `superadmin` **tidak pernah muncul** sebagai pilihan di form Tambah/Edit Akun portal ini (cuma `pmo` & `admin`/"Pemerintah Pusat (Admin)") -- lihat batasan "cuma satu superadmin" di atas. Baris akun `superadmin` sendiri di tabel juga tidak punya tombol Edit/Reset Password/Hapus (backend menolak ketiganya untuk target berrole `superadmin` juga, lihat `admin_update_user`/`admin_delete_user` di `api/main.py`) -- satu-satunya cara mengelola akun superadmin adalah CLI.

Portal ini juga jadi tempat mengganti **provider & API key AI Insight** (`AI_PROVIDER`, `ANTHROPIC_API_KEY`/`GEMINI_API_KEY`, dipakai step 5) tanpa perlu akses shell/redeploy -- kartu "AI Insight -- Provider & API Key" di halaman yang sama, dengan dropdown Anthropic/Gemini terpisah dari field API key (masing-masing provider punya key sendiri, tidak saling menggantikan -- ganti provider dulu, baru isi key untuk provider itu kalau belum pernah diisi). Keduanya disimpan di tabel `settings` (auth.db, lihat `auth/settings_store.py`) dan langsung menimpa `os.environ` proses backend yang sedang jalan (berlaku seketika, tanpa restart), sekaligus dipakai lagi otomatis tiap kali backend di-restart.

Ini butuh dua penyesuaian di `ai_insight/generate_insight.py` supaya benar-benar berlaku tanpa restart: (1) `AI_PROVIDER` yang tadinya konstanta modul (dibaca SEKALI saat import -- proses lama tidak akan pernah melihat perubahan) diganti jadi `_current_provider()`, fungsi kecil yang baca `os.environ` FRESH tiap dipanggil; (2) client LLM di `api/main.py` di-cache satu kali per proses (`_ai_client_cache`, supaya tidak membangun ulang tiap request) -- endpoint `/admin/ai-key` & `/admin/ai-provider` sama-sama mengosongkan cache itu (`_reset_ai_client_cache()`) setelah menyimpan, supaya request `/insight/{id}` BERIKUTNYA membangun client baru dengan key/provider yang baru, bukan client lama yang sudah kadung di-cache.

Kartu yang sama juga punya field **id model** (`CLAUDE_MODEL`/`GEMINI_MODEL`, endpoint `PUT /admin/ai-model`) -- bisa isi SATU id, atau LEBIH DARI SATU dipisah koma sebagai **fallback chain** (mis. `gemini-3.5-flash, gemini-2.5-flash, gemma-4-31b-it`). `_model_candidates()` di `generate_insight.py` mem-parse daftar itu, dan `panggil_claude()`/`panggil_gemini()` mencobanya BERURUTAN dalam satu request `/insight/{id}` yang sama -- kalau kandidat pertama gagal (model belum/tidak tersedia, kuota provider habis, balasan bukan JSON valid, dst), otomatis lanjut ke kandidat berikutnya sebelum benar-benar menyerah (error gabungan SEMUA percobaan baru dilempar kalau kandidat terakhir juga gagal). Id model TIDAK divalidasi di endpoint atau di kode ini -- katalog model tiap provider berubah dari waktu ke waktu (termasuk rilis yang belum diketahui saat kode ini ditulis), jadi validasinya diserahkan ke provider sendiri lewat respons error API yang sebenarnya, bukan dicek terhadap daftar hardcoded yang bisa diam-diam usang.

**Environment Python backend & google-genai:** paket `anthropic` & `google-genai` butuh Python berbeda -- `google-genai` secara spesifik butuh **Python >= 3.10** (lihat komentar di `requirements.txt`), sementara environment dev yang divalidasi awalnya pakai Python 3.8 sistem. Kalau `python3` default di mesin Anda < 3.10, `pip install google-genai` akan gagal ("No matching distribution found") -- buat virtualenv terpisah dengan Python 3.10+ dan jalankan `uvicorn` dari situ, contoh (asumsi Python 3.12 tersedia lewat Homebrew):
```bash
cd backend
python3.12 -m venv .venv312
.venv312/bin/pip install -r requirements.txt google-genai
.venv312/bin/python -m uvicorn api.main:app --reload --reload-dir api --reload-dir auth --reload-dir ai_insight --reload-dir scoring --reload-dir prediction --port 8000
```
`--reload-dir` di sini SENGAJA membatasi folder yang di-watch `--reload` cuma ke source code -- default-nya (tanpa `--reload-dir`) watch SELURUH `backend/`, termasuk `.venv312/` yang berisi ribuan file paket ter-install, memicu reload berulang tiap kali venv itu disentuh.

```bash
cd frontend-admin
npm install
cp .env.example .env   # sesuaikan VITE_API_BASE_URL kalau backend tidak di localhost:8000
npm run dev
```

Buka `http://localhost:5174` -- atau `http://admin.localhost:5174` untuk mensimulasikan subdomain terpisah di lokal (`*.localhost` otomatis resolve ke `127.0.0.1` di OS/browser modern, RFC 6761, tanpa perlu edit `/etc/hosts`; `vite.config.js` di sini sudah meng-allowlist host itu lewat `server.allowedHosts`). Backend API (step 6) harus jalan dengan `CORS_ORIGINS` yang mencakup origin portal ini (lihat contoh di atas), kalau tidak permintaan akan ditolak CORS.

Di produksi, `frontend-admin/` di-build & di-deploy **terpisah** dari `frontend/` (proses `npm run build` sendiri, hasil `dist/` sendiri) ke subdomain administratif Anda -- dua frontend, satu backend yang sama.

### Keterbatasan yang disadari (jujur ke juri, bukan disembunyikan)

- **Rate limit login** (5 percobaan gagal / 5 menit per username) disimpan in-memory di proses API -- cukup untuk demo single-process, tapi TIDAK dibagi antar worker/instance. Kalau step 8 deploy multi-worker, pindahkan ke Redis atau layanan rate-limit terkelola.
- **Token JWT disimpan di `localStorage`** di frontend -- pragmatis untuk tool internal ini, tapi lebih rentan XSS dibanding httpOnly cookie (skrip apa pun yang berjalan di halaman bisa membacanya). Kalau dashboard ini nanti memuat script pihak ketiga, pindahkan penyimpanan token ke httpOnly cookie + CSRF token di backend.
- Tidak ada refresh token -- sesi kedaluwarsa penuh setelah 8 jam, user harus login ulang (cukup untuk pemakaian sehari-hari, bukan sesi yang harus terus aktif berhari-hari).

### Bug yang ditemukan & diperbaiki saat membangun ini

Percobaan pertama, user yang baru login **langsung ter-logout lagi** walau kredensialnya benar (network log: `/auth/login` 200, lalu `/ringkasan` 401, lalu `onUnauthorized()` ter-panggil dan menghapus sesi -- padahal request berikutnya dengan token yang sama sukses 200). Penyebabnya: token di `api.js` di-pasang lewat `useEffect` di `AuthContext` yang baru jalan **setelah** commit + child mount -- jadi halaman yang me-render tepat setelah login (Ringkasan) sempat memanggil API dengan token kosong, dapat 401, dan handler 401 langsung men-logout user itu sebelum token sempat terpasang. Diperbaiki dengan memasang token secara **sinkron** di titik yang sama dengan perubahan state (saat login, saat logout, saat load awal dari `localStorage`) -- bukan didelegasikan ke `useEffect` terpisah yang jadwal eksekusinya tidak dijamin lebih dulu dari efek komponen anak.

## Rencana deployment

Lihat proposal bagian "Gambaran Besar Ide, Metodologi, Tools, dan Teknologi". Kalau target akhirnya VPS (bukan Render/Vercel seperti draf awal), catat: VPS berarti Anda yang mengurus sendiri OS, proses yang tetap menyala (systemd/pm2), reverse proxy (nginx), dan SSL (mis. certbot) — lebih banyak kerja manual dibanding platform terkelola, tapi kerjaan tulis-config-dan-jalankan-perintah seperti ini justru pas dikerjakan bareng AI coding agent.

**Checklist environment variable wajib sebelum deploy publik** (lihat bagian Autentikasi & Otorisasi untuk detail masing-masing):
- `JWT_SECRET` — random panjang, API menolak start tanpa ini. JANGAN reuse nilai dev/lokal.
- `CORS_ORIGINS` — set ke domain **kedua** frontend asli, dipisah koma (dashboard utama + portal superadmin, bukan default `localhost:5173,localhost:5174,admin.localhost:5174`).
- `ANTHROPIC_API_KEY` — kalau step 5 mau jalan sungguhan di server produksi.
- Backup `backend/auth/auth.db` secara terpisah dari `backend/data/output/` — regenerasi data (step 2-4) tidak menyentuhnya, tapi kehilangan disk/volume produksi akan menghapus akun juga kalau tidak di-backup.
