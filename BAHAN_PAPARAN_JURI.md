# Bahan Paparan — SIGAP Kopdes
LAN Datathon 2026 · Subtema: Koperasi dan Pemberdayaan Ekonomi Masyarakat

> Outline ini disusun dari `README.md` proyek + struktur kode yang sudah jadi (step 1-7, step 8 deployment belum). Sesuaikan durasi bicara per bagian dengan slot waktu paparan yang diberikan panitia.

---

## 1. Pembuka — Masalah (1 slide)

**Judul masalah:** Koperasi Desa/Kelurahan Merah Putih (KDMP) baru dibentuk di banyak wilayah, dan pemerintah pusat/PMO tidak punya cara sistematis untuk tahu **mana koperasi yang sedang bermasalah SEBELUM benar-benar kolaps.**

Poin yang perlu disampaikan:
- Pembinaan koperasi selama ini reaktif — masalah ketahuan setelah laporan buruk masuk atau koperasi berhenti beroperasi.
- Tidak ada sistem deteksi dini yang mengubah data transaksi/stok/laporan rutin koperasi menjadi **sinyal risiko** yang bisa ditindaklanjuti.
- Skala masalah: ribuan KDMP tersebar di banyak kabupaten/kota — mustahil dipantau manual satu-satu oleh PMO pusat.

**Kalimat pembuka yang bisa dipakai:** *"Koperasi yang gagal jarang gagal mendadak — ada pola penurunan yang bisa dideteksi berbulan-bulan sebelumnya, kalau saja ada yang membacanya."*

---

## 2. Solusi — SIGAP Kopdes (1 slide)

**SIGAP Kopdes** = **Si**stem **G**agasan/Deteksi Dini Kesehatan Usaha Koperasi Desa (rangkai ulang kepanjangan sesuai proposal asli kalian) — dashboard yang:
1. Menghitung **skor kesehatan** tiap koperasi tiap bulan dari data operasional mentah (transaksi, stok, laporan).
2. **Memprediksi risiko** koperasi jatuh ke kategori Kritis 3 bulan ke depan — bukan cuma snapshot kondisi sekarang.
3. Memberi **rekomendasi tindakan konkret** lewat AI (narasi kondisi, aksi diagnostik, ide produk/promosi/program) — bukan cuma angka mentah yang harus ditafsirkan manual oleh PMO.

**Diferensiasi utama (tekankan ini ke juri):** SIGAP Kopdes bukan sekadar dashboard pelaporan pasif — ada lapisan **prediksi** (step 4) dan **AI insight actionable** (step 5) di atas skor mentahnya. PMO tidak cuma disodori angka, tapi juga saran tindakan spesifik per koperasi.

---

## 3. Bagaimana Cara Kerjanya — Metodologi (perluas ke 3-4 slide, satu per lapisan)

Prinsip yang harus ditekankan di awal bagian ini: **tiga lapisan berjalan berurutan dan satu arah** — tiap lapisan HANYA mengonsumsi hasil lapisan sebelumnya, tidak pernah menghitung ulang sendiri. Ini yang membuat sistemnya bisa diaudit ujung ke ujung.

```
data mentah (transaksi, stok, laporan)
        ↓
[Lapisan 1] Skor Kesehatan  — statistik deskriptif, per periode
        ↓
[Lapisan 2] Prediksi Risiko — regresi logistik, dari histori skor
        ↓
[Lapisan 3] AI Insight      — LLM, menarasikan angka lapisan 1 & 2 (tidak menghitung)
        ↓
   Dashboard (PMO)
```

### 3.1 Lapisan 1 — Skor Kesehatan (`compute_scores.py`)

Dihitung **per koperasi, per bulan**, dari 3 komponen:

| Komponen | Cara hitung | Kenapa begitu |
|---|---|---|
| **Skor Transaksi** | rata-rata **peringkat persentil** dari (a) jumlah transaksi dan (b) total nilai transaksi bulan itu, dibandingkan SELURUH koperasi pada periode yang sama | nilai rupiah transaksi antar-koperasi biasanya *right-skewed* (banyak koperasi kecil, sedikit yang sangat besar) — kalau dipakai interpolasi nilai linear biasa, mayoritas koperasi akan tampak rendah padahal posisi relatifnya biasa saja. Peringkat persentil membuat median populasi selalu ≈ skor 50, apa pun bentuk distribusinya |
| **Skor Stok** | peringkat persentil jumlah unit stok, relatif ke populasi periode yang sama | logika sama seperti di atas |
| **Skor Pelaporan** | `persen_kelengkapan` laporan bulan itu, dipakai LANGSUNG (bukan persentil) | field ini sudah skala 0-100 dengan makna absolut (100% = laporan lengkap) — tidak perlu dan tidak boleh dijadikan relatif |

**Skor komposit** = rata-rata terbobot ketiganya (baseline saat ini: bobot **sama rata 1/3-1/3-1/3**, bisa disetel di konstanta `BOBOT`).

**Kategori:** Sehat (≥70) / Waspada (40-69) / Kritis (<40) — ambang ini juga konstanta yang bisa disetel (`BATAS_SEHAT`, `BATAS_WASPADA`), dan diekspos ke endpoint `/metodologi` supaya dashboard tidak pernah menampilkan angka yang beda dari yang sebenarnya dipakai backend.

**Keterbatasan yang perlu disebut jujur ke juri:** karena berbasis peringkat persentil, skor ini **relatif terhadap populasi koperasi yang dipantau**, bukan skala absolut universal — koperasi dengan skor 50 berarti "median di antara koperasi yang ada", bukan "separuh optimal secara objektif".

**Notifikasi otomatis** diterbitkan dari lapisan ini kalau: (a) kategori jadi Kritis, atau (b) skor turun ≥5 poin dari bulan sebelumnya (ambang `TURUN_SIGNIFIKAN`) — jadi PMO dapat sinyal bahkan sebelum koperasi jatuh ke kategori terburuk.

### 3.2 Lapisan 2 — Prediksi Risiko 3 Bulan (`predict_risk.py`)

- **Model:** regresi logistik (`class_weight="balanced"` karena kasus Kritis biasanya minoritas di data).
- **Target:** apakah koperasi akan berkategori **Kritis 3 bulan dari sekarang** (biner, ya/tidak) — bukan memprediksi skor persis, cukup probabilitas jatuh ke kondisi kritis.
- **6 fitur input:** skor komposit, skor transaksi, skor stok, skor pelaporan (kondisi SAAT INI) + `delta_1bln` dan `delta_2bln` (perubahan skor komposit 1 dan 2 bulan terakhir) — jadi model melihat **arah tren**, bukan cuma snapshot.
- **Cara menyusun data latih:** pasangan periode (bulan-t, bulan-t+3) yang dua-duanya ada di histori (contoh: Maret→Juni, April→Juli, Mei→Agustus) — menghasilkan ratusan contoh pelatihan dari data 6 bulan yang tersedia.
- **Output:** probabilitas 0-100%, diisi ke kolom `prediksi_risiko_3bln` untuk SEMUA baris skor historis (bukan cuma periode terbaru), supaya dashboard tetap punya angka ini di periode manapun yang dilihat pengguna.

**Kejujuran metrik (poin ini WAJIB disampaikan, jangan dilewati):**
- Karena data training berasal dari data simulasi dengan jumlah terbatas, ROC-AUC di sini bersifat **indikatif untuk prototipe**, bukan klaim validasi siap produksi.
- Percobaan pertama sempat menghasilkan **ROC-AUC 0.99** — dicurigai overfitting, karena `generate_data.py` awalnya memberi tiap koperasi satu profil kesehatan tetap sepanjang 6 bulan (memprediksi masa depan jadi nyaris trivial karena masa depan = masa sekarang).
- Diperbaiki dengan menambah **~15% koperasi mengalami "goncangan"** (perubahan tier kesehatan di tengah jalan) di generator data, supaya polanya lebih realistis. Setelah perbaikan, ROC-AUC turun ke **~0.87** — lebih rendah, tapi jauh lebih bisa dipertanggungjawabkan.

**Kalimat kunci untuk slide ini:** *"Kami curiga saat angka terlalu bagus, bukan cuma senang — ROC-AUC 0.99 itu tanda bahaya kebocoran data, bukan prestasi. Setelah investigasi dan perbaikan, angkanya turun tapi jadi jujur."*

### 3.3 Lapisan 3 — AI Insight & Rekomendasi (`generate_insight.py`)

**Guardrail desain paling penting:** prompt ke LLM HANYA berisi angka yang sudah dihitung Lapisan 1 & 2, plus profil wilayah (IDM) dari data mentah — LLM **diinstruksikan eksplisit untuk tidak menghitung ulang atau mengarang angka apa pun**, tugasnya murni menarasikan dan menyarankan.

Input yang dikirim ke LLM per koperasi:
- Kondisi operasional: skor komposit + kategori, 3 sub-skor, delta bulan lalu, proyeksi risiko 3 bulan (dari Lapisan 1 & 2)
- Profil wilayah: status & skor IDM, dimensi sosial/ekonomi/lingkungan, mata pencaharian dominan, keragaman ekonomi, akses pusat perdagangan

Output — 5 hal, dalam format JSON terstruktur (bukan teks bebas, supaya bisa dirender konsisten di dashboard):
1. `narasi` — kondisi koperasi berdasarkan pola sub-skor (2-3 kalimat)
2. `rekomendasi_tindakan` — satu aksi diagnostik konkret untuk PMO
3. `produk_prioritas` — 2-3 ide produk/jasa, dari mata pencaharian & keragaman ekonomi wilayah
4. `rekomendasi_promosi` — satu ide kampanye + momentum waktunya
5. `rekomendasi_program` — 2-3 ide program non-produk (pelatihan, kemitraan, digitalisasi)

**Dua provider dipakai dengan prompt & skema JSON identik** (Claude dan Gemini) — hanya cara panggil API-nya beda, jadi tidak ada dua sumber logika yang harus dirawat terpisah. Ada juga **fallback chain multi-model** per provider: kalau model pertama gagal (kuota habis, JSON tidak valid, dst), otomatis coba model berikutnya sebelum benar-benar menyerah.

**Kalimat kunci untuk juri yang skeptis soal AI:** *"LLM di sini murni lapisan komunikasi — semua angka dihitung dengan metodologi statistik yang transparan dan bisa diaudit di Lapisan 1 dan 2. AI hanya menerjemahkan angka itu jadi bahasa dan saran yang bisa langsung dipakai PMO, tidak pernah jadi sumber angka baru."*

### 3.4 Contoh Konkret End-to-End (opsional, sangat efektif untuk juri)

Kalau ada waktu, jalankan satu contoh koperasi lewat ketiga lapisan di depan juri:
1. "Koperasi X: skor transaksi 35, skor stok 42, skor pelaporan 90 → skor komposit ≈ 55.7 → kategori **Waspada**." *(tunjukkan pelaporan bagus tapi transaksi/stok lemah — pola yang tidak terlihat kalau cuma lihat skor komposit saja)*
2. "Tren turun 2 bulan berturut-turut → model memprediksi **68% risiko jadi Kritis dalam 3 bulan**."
3. "AI insight membaca kedua angka itu dan menyarankan: fokus pembinaan ke pengelolaan stok (bukan pelaporan, yang sudah bagus), plus ide produk berbasis mata pencaharian dominan wilayahnya."

Pola presentasi ini menunjukkan **kenapa 3 lapisan lebih baik dari 1 angka tunggal** — PMO tahu bukan cuma "koperasi ini bermasalah" tapi **di komponen mana, seberapa mendesak, dan apa yang harus dilakukan**.

---

## 4. Kejujuran Soal Data — poin kredibilitas yang justru jadi kekuatan (1 slide)

Juri datathon biasanya sangat menghargai kejujuran soal keterbatasan dibanding klaim berlebihan. Sampaikan ini secara terbuka, jangan disembunyikan:

- **Data operasional (transaksi/stok/laporan) 100% simulasi** — KDMP riil belum punya histori data operasional yang bisa diakses untuk datathon ini.
- **Profil wilayah SEBAGIAN data ASLI**: 13 dari 21 kabupaten/kota pakai data resmi **Indeks Desa Membangun (IDM) 2024** dari Kemendes PDTT (2.822 desa tersaring). 8 kota sisanya simulasi penuh — karena IDM secara definisi memang hanya mencakup desa, bukan kelurahan/kota (kewenangan Kemendagri, bukan Kemendes).
- IDM 2024 adalah data per tahun 2024, bukan real-time — disebutkan apa adanya.
- Model prediksi sempat menghasilkan ROC-AUC 0.99 (dicurigai overfitting akibat data simulasi yang terlalu statis), sudah diperbaiki dengan menambah variasi realistis ("goncangan" tier di ~15% koperasi) → turun ke ~0.87, angka yang lebih bisa dipertanggungjawabkan.

**Kenapa bagian ini penting dipaparkan:** menunjukkan proses berpikir ilmiah (curiga pada hasil yang "terlalu bagus", lalu investigasi & perbaiki) — ini biasanya lebih meyakinkan juri teknis dibanding pura-pura semua sempurna.

---

## 5. Demo Langsung (2-3 slide + demo live/rekaman)

Urutan demo yang disarankan (ikuti alur natural pengguna PMO):
1. **Login** → tunjukkan ada role berbeda (admin = semua wilayah, pmo = scope wilayah tertentu).
2. **Halaman Ringkasan** → stat tile jumlah koperasi per kategori + notifikasi tertunda + **Peta Sebaran Koperasi** (klik provinsi → kabupaten → marker koperasi individual, warna sesuai kategori kesehatan).
3. **Daftar Koperasi** → filter kategori/wilayah, tunjukkan skala data (jumlah koperasi yang bisa dipantau sekaligus, mustahil manual).
4. **Detail Koperasi** → profil, tren skor 4-seri (grafik), lalu **AI Insight** — tunggu proses generate on-demand (~2-15 detik), tunjukkan hasil: narasi kondisi, rekomendasi tindakan, produk prioritas, rekomendasi promosi & program.
5. **Halaman Kriteria & Metodologi** → bukti bahwa ambang skor bukan angka sembarangan, bisa dijelaskan dan diaudit.
6. (Kalau ada waktu) **Portal Superadmin** → manajemen akun, ganti provider/API key AI tanpa redeploy.

**Tips presentasi demo:** siapkan 1-2 koperasi contoh yang sudah pernah dibuka sebelumnya (AI insight-nya sudah ter-cache) supaya tidak menunggu generate live di depan juri kalau koneksi lambat — tapi juga siapkan 1 contoh live generate untuk menunjukkan fiturnya nyata, bukan data yang di-hardcode.

---

## 6. Keamanan & Kesiapan Produksi (1 slide)

Ini pembeda penting dari proyek datathon "sekadar demo" — tunjukkan bahwa tim sudah mikir sampai tahap siap-pakai:

- Autentikasi wajib (JWT, bcrypt password hash), 3 role dengan pemisahan wewenang jelas (admin lihat data, superadmin kelola akun — dipisah sengaja untuk prinsip least privilege).
- Akses PMO dibatasi per wilayah **di level query SQL**, bukan disaring belakangan — data di luar scope tidak pernah keluar dari database.
- Portal superadmin terpisah dari dashboard utama (bisa di-deploy ke subdomain berbeda, tidak publik/tidak ditautkan).
- Ditambahkan **sebelum** rencana deployment publik, karena data kesehatan finansial koperasi bersifat sensitif — bukan tempelan di akhir.

**Kalimat kunci:** *"Kami menambahkan lapisan keamanan ini bukan karena template best-practice, tapi karena sadar begitu sistem ini online, data finansial ratusan koperasi di berbagai wilayah jadi bisa diakses siapa saja yang tahu URL-nya kalau tidak dilindungi."*

---

## 7. Dampak & Manfaat (1 slide)

Sasaran manfaat, kaitkan ke subtema "Koperasi dan Pemberdayaan Ekonomi Masyarakat":
- **Bagi PMO/pembina koperasi:** dari reaktif (menunggu laporan masalah) ke proaktif (intervensi dini berbasis skor & prediksi 3 bulan ke depan).
- **Bagi Pemerintah Pusat:** visibilitas nasional real-time atas kesehatan seluruh jaringan KDMP tanpa perlu laporan manual berjenjang.
- **Bagi koperasi sendiri (efek tidak langsung):** rekomendasi produk/promosi/program yang kontekstual dengan kondisi sosial-ekonomi wilayahnya (bukan saran generik), berpotensi mempercepat pemberdayaan ekonomi lokal.
- **Skalabilitas:** karena skor & prediksi dihitung otomatis dari data operasional rutin, sistem ini bisa scale ke ribuan koperasi tanpa menambah beban kerja manual PMO secara linear.

---

## 8. Status Proyek & Roadmap (1 slide)

Jujur soal apa yang sudah selesai vs belum — biasanya juri bertanya ini langsung:

| Status | Tahap |
|---|---|
| ✅ Selesai | Data layer, engine skor, model prediksi, AI insight, backend API, dashboard React, autentikasi & otorisasi |
| ⏳ Belum | Deployment publik (backend + frontend online agar bisa diakses juri di luar demo lokal) |

Langkah berikutnya kalau lolos ke tahap selanjutnya: deploy ke VPS/platform terkelola, integrasi data KDMP riil (menggantikan data operasional simulasi) begitu tersedia, kemungkinan tambah channel notifikasi (WhatsApp/email) untuk PMO.

---

## 9. Penutup (1 slide)

- Ulangi satu kalimat inti: deteksi dini berbasis data, bukan menunggu laporan masalah.
- Ajakan: kalau dapat slot Q&A, arahkan juri ke bagian yang paling kuat — kejujuran metodologi (bagian 4) dan keamanan (bagian 6) — dua hal yang sering jadi pembeda proyek datathon yang matang dari yang sekadar prototipe.

---

## Antisipasi Pertanyaan Juri (siapkan jawaban singkat)

1. **"Datanya simulasi, bagaimana kami tahu ini akan bekerja di data riil?"**
   → Metodologi skor & model prediksi tidak bergantung pada sumber data spesifik — selama skema data operasional koperasi riil punya field yang setara (transaksi, stok, laporan), pipeline yang sama bisa dipakai langsung. Bagian yang sudah pakai data riil (profil wilayah/IDM) membuktikan arsitekturnya memang dirancang untuk menerima data asli, bukan cuma dummy.

2. **"Kenapa pakai LLM, bukan risikonya berhalusinasi?"**
   → LLM hanya menerima angka yang sudah dihitung, diinstruksikan eksplisit untuk tidak menghitung ulang atau mengarang data — perannya murni narasi & rekomendasi, bukan sumber kebenaran angka.

3. **"Bagaimana kalau API LLM down/kuota habis saat demo ke publik?"**
   → Ada fallback chain multi-model per provider, dua provider didukung (Anthropic & Gemini), dan pesan error yang jelas (bukan crash) kalau semua gagal — skor & prediksi (fitur inti) tetap berjalan independen dari AI insight.

4. **"Seberapa aman data koperasi ini kalau online?"**
   → Lihat bagian 6 — auth wajib, scope wilayah ditegakkan di level database, portal manajemen akun terpisah dari dashboard data.

5. **"Kenapa baru mau deploy sekarang, kok belum online dari awal?"**
   → Karena data ini sensitif, keamanan (autentikasi & otorisasi) sengaja dituntaskan dulu sebelum publikasi, bukan ditambal belakangan setelah online.
