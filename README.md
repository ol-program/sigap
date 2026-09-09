# SIGAP Kopdes

Sistem Deteksi Dini Kelayakan Usaha Koperasi Desa/Kelurahan Merah Putih (KDMP) — dibuat untuk LAN Datathon 2026 (subtema Koperasi dan Pemberdayaan Ekonomi Masyarakat).

Dokumen lengkap: lihat `Proposal_SIGAP_Kopdes_LAN_Datathon_2026.docx`.

## Status

- [x] **1. Struktur proyek & rencana teknis**
- [x] **2. Data layer** — generator data simulasi sesuai skema (`backend/data/generate_data.py`)
- [x] **3. Engine skor kelayakan** — skor komposit dari data mentah (`backend/scoring/compute_scores.py`)
- [x] **4. Model prediksi risiko** — proyeksi risiko kritis 3 bulan ke depan (`backend/prediction/predict_risk.py`)
- [x] **5. AI Insight & Rekomendasi** — narasi kondisi + saran tindakan per koperasi (`backend/ai_insight/generate_insight.py`)
- [x] **6. Backend API** — FastAPI yang menyajikan skor, prediksi, dan insight AI (`backend/api/main.py`)
- [x] **7. Dashboard React** — terhubung ke API step 6 (`frontend/`)
- [x] **Autentikasi & Otorisasi** — login wajib, akses PMO dibatasi per wilayah (`backend/auth/`)
- [x] **8. Deployment** — live di VPS (lihat `deploy/`):
  - Dashboard: https://sigapkopdes.duckdns.org
  - Portal superadmin: https://adminsigapkopdes.duckdns.org
  - API: https://apisigapkopdes.duckdns.org/docs

Step 5 (AI Insight) dibangun setelah 3 & 4 karena menarasikan skor dan proyeksi risiko yang **sudah dihitung** — LLM diberi angka jadi, tugasnya menjelaskan dan menyarankan tindakan, bukan menghitung sendiri.

## Struktur folder

```
sigap-kopdes/
├── README.md
├── backend/
│   ├── requirements.txt
│   ├── data/
│   │   ├── generate_data.py       # step 2
│   │   ├── prepare_idm_lookup.py  # sekali-jalan: saring data IDM asli
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
│       └── auth.db                # users -- terpisah dari sigap_kopdes.db
├── frontend/                      # step 7: dashboard React (Vite) -- role admin & pmo
└── frontend-admin/                # portal superadmin (React/Vite) terpisah -- manajemen akun
```

## Alur baca kode

Dari fondasi ke lapisan paling atas — tiap file dibangun di atas file sebelumnya:

1. `backend/data/generate_data.py` — struktur data & cara data disimulasikan
2. `backend/scoring/compute_scores.py` — cara skor kelayakan dihitung dari data mentah
3. `backend/prediction/predict_risk.py` — model prediksi risiko
4. `backend/ai_insight/generate_insight.py` — lapisan AI, mengonsumsi hasil 1-3; lihat `PROMPT_TEMPLATE` untuk isi persis yang dikirim ke LLM
5. `backend/api/main.py` — lapisan API, murni query/join dari `sigap_kopdes.db`
6. `frontend/src/` — dashboard React, mulai dari `App.jsx` (routing) lalu `pages/`

## Menjalankan step 2 (data simulasi)

```bash
cd backend
pip install -r requirements.txt   # belum ada dependency eksternal di step ini
python data/generate_data.py
```

Output: `backend/data/output/sigap_kopdes.db` (SQLite, 6 tabel sesuai skema termasuk `profil_wilayah`) dan file `.csv` per tabel.

Data operasional (TRANSAKSI/STOK/LAPORAN/KOPERASI) simulasi 100% — KDMP sungguhan belum ada di dataset ini. `wilayah` menyimpan `latitude`/`longitude` (titik pusat kabupaten/kota asli + sebaran acak kecil per desa) untuk halaman Peta di step 7 — provinsi & kabupaten/kota memang nama wilayah Indonesia sungguhan, hanya desa/kelurahan fiktif untuk sebagian wilayah.

`profil_wilayah` sebagian memakai data asli: *Indeks Desa Membangun (IDM) 2024 hasil pemutakhiran* (Kemendes PDTT), disaring lewat:

```bash
cd backend/data
pip install openpyxl   # cuma dipakai sekali di sini, tidak masuk requirements.txt
python prepare_idm_lookup.py "/path/ke/indeks-desa-membangun-2024....xlsx"
```

Menghasilkan `idm_2024_lookup.csv` (sudah ada di repo, langkah ini opsional kecuali ganti/perbarui file sumber) yang dibaca `generate_data.py` tiap dijalankan. Untuk 13 dari 21 kabupaten/kota di `WILAYAH_SEED` berstatus "Kabupaten", nama desa + dimensi sosial/ekonomi/lingkungan + status/skor IDM di `profil_wilayah` diambil dari data asli IDM 2024 (2.822 desa tersaring). 8 kabupaten/kota berstatus "Kota" tetap simulasi penuh — IDM secara definisi hanya mencakup desa (kewenangan Kemendes PDTT), bukan kelurahan (kewenangan Kemendagri). `mata_pencaharian_dominan`, `ekonomi_beragam`, `akses_pusat_perdagangan` tetap simulasi untuk semua wilayah (tidak ada di sumber IDM). Data IDM 2024 adalah data per 2024, bukan real-time.

Kalau database lama dibuat sebelum perubahan lat/lon & IDM asli ini: jalankan ulang `generate_data.py` lalu `compute_scores.py` dan `predict_risk.py` (step 3 & 4) — `generate_data.py` menghapus & menulis ulang seluruh `sigap_kopdes.db` tiap dijalankan, jadi tabel `skor_kelayakan`/`notifikasi`/`ai_insight` ikut hilang dan perlu dihitung ulang (tabel `users` di `auth.db` aman, disimpan terpisah).

## Menjalankan step 3 (engine skor kelayakan)

```bash
cd backend
python scoring/compute_scores.py   # butuh pandas: pip install pandas
```

Membaca tabel mentah dari `sigap_kopdes.db`, menghitung skor 0-100 per koperasi per bulan (metodologi lengkap ada di docstring `compute_scores.py`), lalu menulis tabel `skor_kelayakan` dan `notifikasi`.

Parameter yang bisa disetel (di bagian atas file): bobot tiap komponen skor (`BOBOT`), ambang kategori (`BATAS_SEHAT`, `BATAS_WASPADA`), ambang notifikasi penurunan skor (`TURUN_SIGNIFIKAN`).

## Menjalankan step 4 (model prediksi risiko)

```bash
cd backend
python prediction/predict_risk.py   # butuh scikit-learn, joblib
```

Melatih regresi logistik dari histori skor (fitur: skor komposit + 3 sub-skor + tren 1 & 2 bulan terakhir) untuk memprediksi probabilitas sebuah koperasi jatuh ke kategori Kritis 3 bulan ke depan, lalu mengisi kolom `prediksi_risiko_3bln` di tabel `skor_kelayakan`.

Data simulasi dan jumlahnya terbatas (ROC-AUC ~0.87 pada data uji) — metrik ini indikatif untuk prototipe, bukan validasi produksi.

## Menjalankan step 5 (AI Insight & Rekomendasi)

Tiga provider LLM didukung, dipilih lewat env var `AI_PROVIDER` (default `anthropic`) — `PROMPT_TEMPLATE` dan skema JSON keluarannya sama persis untuk ketiganya, cuma cara memanggil API-nya yang beda:

```bash
cd backend
pip install -r requirements.txt   # perlu paket anthropic (default)

# 1. Cek dulu prompt & alur datanya tanpa memanggil API (gratis, provider apa pun):
python ai_insight/generate_insight.py --dry-run --koperasi KDMP-00001

# 2a. Pakai Claude (default) -- perlu API key berbayar:
export ANTHROPIC_API_KEY=sk-ant-...
python ai_insight/generate_insight.py --koperasi KDMP-00001   # satu koperasi
python ai_insight/generate_insight.py                          # semua koperasi, periode terbaru

# 2b. Atau pakai Gemini Flash -- gratis, tanpa kartu kredit untuk tier gratis:
pip install google-genai   # butuh Python >= 3.10 (cek: python3 --version)
export AI_PROVIDER=gemini
export GEMINI_API_KEY=...   # bikin di https://aistudio.google.com/apikey
python ai_insight/generate_insight.py --koperasi KDMP-00001

# 2c. Atau pakai Ollama Cloud (model gemma4:cloud, default) -- dipanggil
# lewat HTTPS ke ollama.com, bukan server Ollama lokal, jadi tidak perlu
# install/jalankan `ollama serve` di server backend ini:
pip install ollama
export AI_PROVIDER=ollama
export OLLAMA_API_KEY=...   # bikin di https://ollama.com/settings/keys
python ai_insight/generate_insight.py --koperasi KDMP-00001
```

Kalau `python3` sistem lebih lama dari 3.10 (paket `google-genai` menolak versi di bawah itu): cek dulu apakah ada Python versi lebih baru sudah terpasang sebelum install versi baru — pakai `python3.12 -m venv .venv && source .venv/bin/activate` supaya tidak menimpa `python3` default sistem.

Kuota & syarat tier gratis Gemini bisa berubah — cek angka terkini di [ai.google.dev/gemini-api/docs/rate-limits](https://ai.google.dev/gemini-api/docs/rate-limits). Model yang dipakai (`GEMINI_MODEL` di `generate_insight.py`) juga bisa perlu di-update seiring waktu.

`simpan()` melakukan UPSERT per `(koperasi_id, periode)`, bukan menimpa total tabel `ai_insight` — menjalankan `--koperasi X` untuk satu koperasi tidak menghapus insight koperasi lain yang sudah tersimpan.

### Generate on-demand lewat dashboard (bukan cuma batch CLI)

Cara di atas (CLI, `--koperasi`/batch semua) tetap ada, tapi bukan satu-satunya jalan. `backend/api/main.py` generate insight realtime begitu dashboard membuka halaman detail koperasi yang belum pernah punya insight tersimpan — endpoint `GET /insight/{koperasi_id}` cek cache dulu, kalau kosong baru panggil LLM saat itu juga (~2-15 detik tergantung provider), simpan hasilnya, lalu kunjungan berikutnya ke koperasi yang sama langsung dari cache. Ini supaya kuota API cuma terpakai untuk koperasi yang benar-benar dilihat pengguna.

Konsekuensinya: backend API (step 6) butuh API key provider yang sama seperti CLI (`ANTHROPIC_API_KEY`, atau `GEMINI_API_KEY` + `AI_PROVIDER=gemini`, atau `OLLAMA_API_KEY` + `AI_PROVIDER=ollama`) di environment-nya saat dijalankan — kalau belum di-set, endpoint balas `503` dengan pesan jelas, dan frontend menampilkan pesan yang sama ke pengguna. Panggilan LLM yang gagal (rate limit, jaringan, dst) diringkas jadi satu pesan Indonesia yang jelas (`ringkas_error_llm()` di `api/main.py`), bukan dump error mentah dari provider.

Di frontend, kartu AI Insight (`src/components/AiInsightCard.jsx`) menampilkan skeleton shimmer + indikator "sedang berpikir" selagi generate berlangsung, lalu tiap kartu hasil muncul dengan animasi fade-in bertahap (kartu yang sudah di-cache tampil langsung tanpa animasi). Menghormati `prefers-reduced-motion`.

Menghasilkan 5 hal per koperasi (disimpan ke tabel `ai_insight`):
- `narasi` — kondisi koperasi, dari skor & tren (step 3-4)
- `rekomendasi_tindakan` — satu aksi diagnostik konkret untuk PMO
- `produk_prioritas` — array 2-3 ide produk/jasa, dari mata pencaharian dominan & keragaman ekonomi wilayah (`profil_wilayah`)
- `rekomendasi_promosi` — satu ide kampanye/promosi konkret + momentum waktunya
- `rekomendasi_program` — array 2-3 ide program non-produk (pelatihan, kemitraan, digitalisasi, dst.), dari dimensi sosial/ekonomi/lingkungan & akses pasar wilayah

`produk_prioritas` & `rekomendasi_program` disimpan sebagai JSON array di kolom TEXT (SQLite tidak punya tipe list) — diurai balik jadi array asli oleh backend API sebelum dikirim ke frontend.

Prinsip desain: prompt hanya berisi angka yang sudah dihitung `compute_scores.py`, `predict_risk.py`, dan profil wilayah dari `generate_data.py` — LLM diinstruksikan eksplisit untuk tidak menghitung ulang atau mengarang data wilayah baru, cuma menarasikan & menyarankan. `PROMPT_TEMPLATE` identik untuk ketiga provider. Project ini tidak mengintegrasikan API IDM/pemerintah sungguhan — seluruh dataset memang simulasi, jadi "data eksternal" di sini berhenti di simulasi `profil_wilayah` dari step 2.

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
| `GET /skor` | Baris `skor_kelayakan` mentah (filter: `periode`, `koperasi_id`) |
| `GET /notifikasi` | Notifikasi otomatis dari step 3 (filter: `status_tindak_lanjut`, `koperasi_id`) |
| `GET /insight/{koperasi_id}` | AI insight -- dari cache kalau sudah ada, atau generate on-demand kalau belum. 503 kalau server belum ada API key provider, 502 kalau panggilan LLM gagal |
| `GET /wilayah` | Daftar wilayah + profil IDM gabungan |
| `GET /ringkasan` | Agregat untuk kartu dashboard (jumlah per kategori, rata-rata skor, notifikasi belum ditindaklanjuti) |
| `GET /peta/provinsi` | Agregat kelayakan per provinsi (level 1 peta) -- jumlah koperasi, rata-rata skor, kategori agregat, koordinat |
| `GET /peta/kabupaten?provinsi=...` | Agregat kelayakan per kabupaten/kota dalam satu provinsi (level 2 peta) |
| `GET /metodologi` | Ambang & bobot skor (`BATAS_SEHAT`, `BATAS_WASPADA`, `BOBOT`, `TURUN_SIGNIFIKAN`, `GAP_BULAN_PREDIKSI`) untuk halaman "Kriteria & Metodologi", diambil langsung dari `compute_scores.py`/`predict_risk.py` |

Kategori agregat di `/peta/*` dihitung dari skor rata-rata wilayah dengan ambang yang sama seperti skor individual (`BATAS_SEHAT`/`BATAS_WASPADA`, di-import langsung dari `scoring/compute_scores.py`) — bukan berarti semua koperasi di wilayah itu senyatanya berkategori sama, cuma penyederhanaan untuk tampilan agregat.

API ini murni membaca & menyusun ulang data dari `sigap_kopdes.db` — tidak menghitung skor/prediksi/insight sendiri. Endpoint `/insight/*` menoleransi tabel `ai_insight` yang belum ada (404 yang jelas, bukan error 500), karena tabel itu baru terisi setelah step 5 dijalankan sungguhan.

Semua endpoint di atas (kecuali `/`) butuh login — lihat bagian "Autentikasi & Otorisasi" di bawah. `CORS_ORIGINS` tidak wildcard `"*"`, default ke `http://localhost:5173` (bisa diubah lewat environment variable, dipisah koma untuk lebih dari satu origin).

## Menjalankan step 7 (Dashboard React)

```bash
cd frontend
npm install
cp .env.example .env   # sesuaikan VITE_API_BASE_URL kalau API tidak di localhost:8000
npm run dev
```

Buka http://localhost:5173 — pastikan backend API (step 6) sudah jalan di port 8000 lebih dulu. Anda akan diarahkan ke `/login` dulu sebelum bisa lihat dashboard apa pun.

Halaman yang ada: **Ringkasan** (stat tile jumlah per kategori + notifikasi tertunda, dan **Peta Sebaran Koperasi** sebagai bagian dari halaman ini), **Daftar Koperasi** (tabel dengan filter kategori/wilayah), **Detail Koperasi** (profil + tren skor 4-seri + kartu AI insight, di-generate on-demand realtime saat pertama kali dibuka — `src/components/AiInsightCard.jsx`), **Notifikasi** (filter status, diambil dinamis dari data yang ada — belum ada enum resmi untuk `status_tindak_lanjut`), **Kriteria & Metodologi** (penjelasan kategori Sehat/Waspada/Kritis, cara hitung skor komposit, arti proyeksi risiko, dan status IDM — dengan tooltip ikon "ⓘ" di titik-titik terkait pada halaman lain, `src/components/InfoTooltip.jsx`).

**Peta** (bagian dari Ringkasan, komponen `src/components/PetaWilayah.jsx`): klik lingkaran provinsi → zoom & tampilkan lingkaran per kabupaten/kota di provinsi itu → klik lagi → tampilkan marker tiap koperasi (warna = kategori skor terbaru), klik marker koperasi untuk buka halaman detailnya. Ukuran lingkaran agregat sebanding jumlah koperasi (skala akar kuadrat), warnanya dari kategori agregat. Butuh akses internet saat runtime untuk memuat tile OpenStreetMap (`{s}.tile.openstreetmap.org`); atribusi OSM sudah ada di pojok kanan-bawah peta. Warna status di peta pakai hex tetap (`src/statusColors.js`), tidak ikut tema gelap/terang, karena tile peta selalu berlatar terang. Untuk akun `pmo`, peta & seluruh isi Ringkasan otomatis terbatas ke wilayah scope-nya (difilter di backend, bukan disembunyikan di frontend).

Kalau Node.js sistem lebih lama dari 20/22 (tooling Vite/`create-vite` terbaru butuh itu) dan Node yang lebih baru terpasang lewat Homebrew tapi belum di-`brew link`, jalankan dengan menambahkan `PATH` sementara:
```bash
export PATH="$(brew --prefix node)/libexec/bin:$(brew --prefix node)/bin:$PATH"
```

## Autentikasi & Otorisasi

Dashboard menampilkan data sensitif (kondisi finansial tiap koperasi di banyak wilayah) dan step 8 mem-publikasikan API ini ke internet, jadi login wajib dan akses PMO dibatasi per wilayah. Dashboard tetap murni read-only — tidak ada form input atau endpoint `POST`/`PUT`/`DELETE` untuk data koperasi; yang ditambahkan di sini hanya lapisan akses.

### Desain

- **Tabel `users` di `auth.db`, terpisah dari `sigap_kopdes.db`** — supaya akun tidak ikut terhapus tiap kali `generate_data.py` menulis ulang total database data.
- **Password di-hash dengan bcrypt**, tidak pernah disimpan/di-log plain text.
- **Sesi berbasis JWT** (stateless), berlaku 8 jam, payload berisi `username`, `role`, dan `scope` wilayah.
- **Tiga role:**
  - `admin` — akses semua wilayah data koperasi, tanpa filter. Tidak bisa membuat/menghapus akun atau reset password orang lain. Ditampilkan sebagai "Pemerintah Pusat (Admin)" di UI, walau nilai `role` di database tetap `admin`.
  - `pmo` — dibatasi ke daftar `kode_wilayah` di kolom `kode_wilayah_scope`. Filter diterapkan di lapisan SQL (`WHERE kode_wilayah IN (...)`, lihat `scope_clause()` di `auth/auth.py`), bukan disaring belakangan di Python. PMO tanpa scope (kosong) fail closed (tidak lihat apa pun), bukan fail open.
  - `superadmin` — hanya bisa mengelola akun & API key AI Insight (lewat `frontend-admin/`), dan tidak bisa lihat data koperasi sama sekali. Cuma boleh ada satu superadmin: endpoint `/admin/users` (POST/PUT) menolak `role=superadmin` sama sekali, supaya superadmin yang sedang login tidak bisa membuat superadmin lain lewat portalnya sendiri. Satu-satunya jalan untuk (mengganti) superadmin adalah CLI `create_user.py --role superadmin`.
  - Koperasi/insight di luar scope PMO dikembalikan sebagai 404 (bukan 403) — supaya tidak membocorkan ke PMO bahwa suatu `koperasi_id` sebenarnya ada di wilayah lain.
- **Wajib ganti password saat login pertama** (`must_change_password`) — akun baru dan akun yang di-reset passwordnya selalu dibuat dengan flag ini menyala. Dicek fresh dari `auth.db` tiap request, bukan dari isi token JWT.
- **Tidak ada halaman registrasi mandiri** — akun dibuat lewat CLI (paling awal, buat akun superadmin pertama) atau lewat portal superadmin sesudahnya:

```bash
cd backend
export JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")   # wajib, lihat di bawah
export CORS_ORIGINS=http://localhost:5173,http://localhost:5174,http://admin.localhost:5174   # lihat "Portal Superadmin"

# Akun superadmin pertama (wajib dibuat lewat CLI):
python auth/create_user.py --username superadmin --role superadmin

# Akun admin (akses semua wilayah data koperasi, bukan manajemen akun):
python auth/create_user.py --username admin --role admin

# Akun PMO dibatasi satu kabupaten/kota (resolve otomatis semua
# kode_wilayah di kabupaten itu dari sigap_kopdes.db):
python auth/create_user.py --username pmo_bandung --role pmo --kabupaten "Kab. Bandung"
```

Password diminta lewat prompt tersembunyi (tidak lewat argumen command line). Menjalankan ulang dengan `--username` yang sama meng-UPSERT (ganti password/scope), bukan menduplikasi akun, dan selalu menyalakan lagi `must_change_password`.

### `JWT_SECRET` wajib di-set

API menolak start kalau `JWT_SECRET` kosong — tidak ada default tertanam di kode. Generate sekali lalu simpan di environment (jangan pernah commit nilai ini ke git):

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

Login lewat `POST /auth/login` (body JSON `{"username", "password"}`) mengembalikan `{access_token, token_type, role, scope, must_change_password}`. Sertakan `Authorization: Bearer <access_token>` di semua request endpoint lain — `frontend/src/api.js` & `AuthContext.jsx` (dan versi ringkasnya di `frontend-admin/`) sudah menangani ini otomatis (token disimpan, dipasang ke tiap request, auto-logout kalau server balas 401, redirect ke halaman ganti password kalau perlu).

### Portal Superadmin (Manajemen Akun) — `frontend-admin/`

App React terpisah dengan build & deployment sendiri, supaya bisa ditaruh di subdomain yang tidak publik/tidak ditautkan dari mana pun (mis. `admin.domain-anda.com` vs `domain-anda.com` untuk dashboard biasa). Login di portal ini menolak akun yang bukan `superadmin`, dan sebaliknya login dashboard utama menolak akun `superadmin` — ditegakkan di frontend dan backend (endpoint `/admin/*` benar-benar 403 kalau bukan superadmin).

Role `superadmin` tidak pernah muncul sebagai pilihan di form Tambah/Edit Akun portal ini. Baris akun `superadmin` sendiri di tabel juga tidak punya tombol Edit/Reset Password/Hapus — satu-satunya cara mengelola akun superadmin adalah CLI.

Portal ini juga jadi tempat mengganti provider & API key AI Insight (`AI_PROVIDER`, `ANTHROPIC_API_KEY`/`GEMINI_API_KEY`/`OLLAMA_API_KEY`) tanpa perlu akses shell/redeploy — kartu "AI Insight — Provider & API Key", dengan dropdown provider terpisah dari field API key (masing-masing provider punya key sendiri). Disimpan di tabel `settings` (auth.db, lihat `auth/settings_store.py`) dan langsung menimpa `os.environ` proses backend yang sedang jalan (berlaku seketika, tanpa restart), sekaligus dipakai lagi otomatis tiap kali backend di-restart.

Kartu yang sama juga punya field id model (`CLAUDE_MODEL`/`GEMINI_MODEL`/`OLLAMA_MODEL`, endpoint `PUT /admin/ai-model`) — bisa isi satu id, atau lebih dari satu dipisah koma sebagai fallback chain (mis. `gemini-3.5-flash, gemini-2.5-flash`). Kalau kandidat pertama gagal (model tidak tersedia, kuota habis, dst), otomatis lanjut ke kandidat berikutnya. Id model tidak divalidasi di endpoint — katalog model tiap provider berubah dari waktu ke waktu, validasinya diserahkan ke provider sendiri lewat error API.

**Environment Python backend:** `google-genai` butuh Python >= 3.10, sementara environment dev awal pakai Python 3.8 sistem. Kalau `python3` default < 3.10, `pip install google-genai` akan gagal — buat virtualenv terpisah dengan Python 3.10+:
```bash
cd backend
python3.12 -m venv .venv312
.venv312/bin/pip install -r requirements.txt google-genai
.venv312/bin/python -m uvicorn api.main:app --reload --reload-dir api --reload-dir auth --reload-dir ai_insight --reload-dir scoring --reload-dir prediction --port 8000
```
`--reload-dir` di sini membatasi folder yang di-watch `--reload` cuma ke source code — tanpa itu, `--reload` watch seluruh `backend/` termasuk `.venv312/`, memicu reload berulang tiap kali venv disentuh.

```bash
cd frontend-admin
npm install
cp .env.example .env   # sesuaikan VITE_API_BASE_URL kalau backend tidak di localhost:8000
npm run dev
```

Buka `http://localhost:5174` — atau `http://admin.localhost:5174` untuk mensimulasikan subdomain terpisah di lokal (`*.localhost` otomatis resolve ke `127.0.0.1`, RFC 6761; `vite.config.js` sudah meng-allowlist host itu lewat `server.allowedHosts`). Backend API harus jalan dengan `CORS_ORIGINS` yang mencakup origin portal ini.

Di produksi, `frontend-admin/` di-build & di-deploy terpisah dari `frontend/` ke subdomain administratif — dua frontend, satu backend yang sama.

### Keterbatasan yang disadari

- **Rate limit login** (5 percobaan gagal / 5 menit per username) disimpan in-memory di proses API — cukup untuk demo single-process, tidak dibagi antar worker/instance. Kalau deploy multi-worker, pindahkan ke Redis atau layanan rate-limit terkelola.
- **Token JWT disimpan di `localStorage`** di frontend — pragmatis untuk tool internal ini, tapi lebih rentan XSS dibanding httpOnly cookie. Kalau dashboard ini nanti memuat script pihak ketiga, pindahkan penyimpanan token ke httpOnly cookie + CSRF token di backend.
- Tidak ada refresh token — sesi kedaluwarsa penuh setelah 8 jam, user harus login ulang.

## Rencana deployment

Target: VPS — nginx sebagai reverse proxy + static file server untuk dua frontend, systemd untuk proses backend, certbot untuk SSL. Config lengkap ada di `deploy/`:

```
deploy/
├── README.md                              # checklist provisioning VPS langkah demi langkah
├── deploy.sh                               # dijalankan CI/CD (atau manual) tiap deploy: git pull, build, restart
├── systemd/sigap-kopdes-backend.service    # proses uvicorn yang tetap menyala + auto-restart
└── nginx/
    ├── dashboard.conf   # frontend/ (dashboard utama)
    ├── admin.conf       # frontend-admin/ (portal superadmin)
    └── api.conf         # reverse proxy ke backend (subdomain terpisah, bukan path /api/ --
                          # arsitekturnya CORS full-origin, lihat frontend/src/api.js)
```

**CI/CD** (`.github/workflows/`): `ci.yml` build-check kedua frontend + import-check backend tiap push/PR. `deploy.yml` SSH ke VPS dan jalankan `deploy/deploy.sh` tiap kali `ci.yml` di branch `main`/`master` sukses — baru aktif setelah secrets `VPS_HOST`/`VPS_USER`/`VPS_SSH_KEY` diisi di GitHub (lihat `deploy/README.md`).

**Kredensial produksi tidak pernah lewat git atau CI/CD** — `backend/.env.production`, `frontend/.env.production`, `frontend-admin/.env.production` (masing-masing ada `.env.production.example` sebagai template yang di-commit) di-copy manual sekali ke VPS lewat `scp`, lalu diisi langsung di file itu di server. Checklist isinya:
- `JWT_SECRET` — random panjang, API menolak start tanpa ini. Jangan reuse nilai dev/lokal.
- `CORS_ORIGINS` — domain kedua frontend asli, dipisah koma (dashboard utama + portal superadmin).
- `VITE_API_BASE_URL` (di kedua frontend) — domain `api.conf`.
- `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` / `OLLAMA_API_KEY` — kalau step 5 mau jalan sungguhan di server produksi.
- Backup `backend/auth/auth.db` secara terpisah dari `backend/data/output/` — regenerasi data (step 2-4) tidak menyentuhnya, tapi kehilangan disk/volume produksi akan menghapus akun juga kalau tidak di-backup.

Urutan lengkap provisioning (server baru, DNS/DuckDNS, systemd, nginx, certbot, akun pertama): lihat `deploy/README.md`.
