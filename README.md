# SIGAP Kopdes

Sistem Deteksi Dini Kelayakan Usaha Koperasi Desa/Kelurahan Merah Putih (KDMP) — dashboard yang menghitung skor kelayakan, memprediksi risiko, dan menghasilkan rekomendasi AI untuk memantau kondisi koperasi desa/kelurahan secara terpusat. Dibuat untuk LAN Datathon 2026 (subtema Koperasi dan Pemberdayaan Ekonomi Masyarakat).

Live: https://sigapkopdes.duckdns.org (dashboard) · https://adminsigapkopdes.duckdns.org (portal superadmin) · https://apisigapkopdes.duckdns.org/docs (API)

Panduan penggunaan dashboard: lihat [`PEDOMAN_PENGGUNAAN.md`](PEDOMAN_PENGGUNAAN.md).

## Struktur Proyek

```
sigap-kopdes/
├── backend/
│   ├── data/            # generator data simulasi -> sigap_kopdes.db
│   ├── scoring/         # hitung skor kelayakan komposit
│   ├── prediction/      # model prediksi risiko 3 bulan ke depan
│   ├── ai_insight/      # narasi & rekomendasi via LLM (Anthropic/Gemini/Ollama)
│   ├── auth/            # login, JWT, manajemen akun (auth.db terpisah)
│   └── api/             # FastAPI yang menyajikan semuanya ke frontend
├── frontend/            # dashboard utama (React + Vite) — role Admin & PMO
├── frontend-admin/      # portal superadmin (React + Vite) — manajemen akun
└── deploy/              # config nginx, systemd, dan checklist deploy VPS
```

## Instalasi

### 1. Backend

```bash
cd backend
pip install -r requirements.txt
python data/generate_data.py          # generate data simulasi -> sigap_kopdes.db
python scoring/compute_scores.py      # hitung skor kelayakan
python prediction/predict_risk.py     # hitung prediksi risiko
```

Set environment variable wajib sebelum menjalankan API:

```bash
export JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
export CORS_ORIGINS=http://localhost:5173,http://localhost:5174
```

Jalankan API:

```bash
uvicorn api.main:app --reload --port 8000
```

Dokumentasi API (Swagger UI): http://localhost:8000/docs

Buat akun pertama (superadmin) lewat CLI, akun lain (Admin/PMO) bisa dibuat lewat portal superadmin sesudahnya:

```bash
python auth/create_user.py --username superadmin --role superadmin
```

### 2. Dashboard (frontend)

```bash
cd frontend
npm install
cp .env.example .env   # sesuaikan VITE_API_BASE_URL kalau API tidak di localhost:8000
npm run dev
```

Buka http://localhost:5173

### 3. Portal Superadmin (frontend-admin)

```bash
cd frontend-admin
npm install
cp .env.example .env   # sesuaikan VITE_API_BASE_URL kalau API tidak di localhost:8000
npm run dev
```

Buka http://localhost:5174

### AI Insight (opsional)

Rekomendasi AI butuh API key salah satu provider — set di environment backend, atau isi lewat kartu "AI Insight — Provider & API Key" di portal superadmin:

```bash
export ANTHROPIC_API_KEY=sk-ant-...       # default provider
# atau
export AI_PROVIDER=gemini
export GEMINI_API_KEY=...
# atau
export AI_PROVIDER=ollama
export OLLAMA_API_KEY=...
```

## Cara Penggunaan

1. Superadmin login di portal superadmin (`frontend-admin`), membuat akun Admin dan/atau PMO.
2. Admin/PMO login di dashboard utama (`frontend`), ganti password saat login pertama.
3. Dashboard menampilkan Ringkasan (statistik + peta sebaran koperasi), Daftar Koperasi, Detail Koperasi (skor, tren, dan AI Insight yang di-generate otomatis), Notifikasi, serta Kriteria & Metodologi.

Panduan lengkap tiap halaman ada di [`PEDOMAN_PENGGUNAAN.md`](PEDOMAN_PENGGUNAAN.md). Untuk deployment ke VPS, lihat [`deploy/README.md`](deploy/README.md).
