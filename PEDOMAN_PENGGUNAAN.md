# Pedoman Penggunaan SIGAP Kopdes

Sistem Deteksi Dini Kelayakan Usaha Koperasi Desa/Kelurahan Merah Putih (KDMP)

---

## 1. Tentang Sistem

SIGAP Kopdes adalah dashboard yang membantu Pemerintah Pusat dan PMO (Pelaksana Monitoring dan Operasional) memantau kondisi ribuan koperasi desa/kelurahan secara terpusat. Sistem ini terdiri dari tiga lapisan yang berjalan berurutan:

1. **Skor Kelayakan** — dihitung otomatis tiap bulan dari data operasional koperasi (transaksi, stok, laporan).
2. **Prediksi Risiko** — memproyeksikan peluang sebuah koperasi jatuh ke kategori Kritis dalam 3 bulan ke depan.
3. **AI Insight & Rekomendasi** — narasi kondisi dan saran tindakan konkret per koperasi, dihasilkan oleh AI berdasarkan skor dan proyeksi di atas.

Sistem ini memiliki **dua portal terpisah**:

| Portal | Alamat | Untuk siapa |
|---|---|---|
| Dashboard utama | `https://sigapkopdes.duckdns.org` | Admin (Pemerintah Pusat) dan PMO (Pelaksana Monitoring dan Operasional) |
| Manajemen Akun | `https://adminsigapkopdes.duckdns.org` | Superadmin saja |

Ada tiga peran (role) pengguna:

- **Superadmin** — hanya boleh ada satu di seluruh sistem. Tugasnya murni mengelola akun login (membuat/mengedit/menghapus akun Admin dan PMO (Pelaksana Monitoring dan Operasional)), bukan melihat data koperasi. Login lewat portal Manajemen Akun.
- **Admin (Pemerintah Pusat)** — akses ke data seluruh koperasi di semua wilayah. Login lewat dashboard utama.
- **PMO (Pelaksana Monitoring dan Operasional)** — akses dibatasi hanya ke koperasi di wilayah (kabupaten/kota) yang ditugaskan padanya. Login lewat dashboard utama.

Tidak ada pendaftaran akun mandiri di sistem ini — semua akun dibuat oleh superadmin.

---

## 2. Tahap Awal: Membuat Akun Superadmin

Akun superadmin adalah satu-satunya akun yang **tidak** dibuat lewat portal web, karena dialah yang nantinya membuat semua akun lain. Akun ini dibuat sekali lewat perintah di server, saat sistem pertama kali di-deploy.

Langkah-langkahnya (dilakukan oleh pihak yang memiliki akses ke server):

1. Masuk ke server tempat SIGAP Kopdes di-deploy.
2. Masuk ke folder backend sistem, lalu jalankan:

   ```
   python backend/auth/create_user.py --username <nama_superadmin> --role superadmin
   ```

3. Sistem akan meminta password lewat prompt tersembunyi (tidak tampil di layar saat diketik), dua kali untuk konfirmasi. Password minimal 8 karakter.
4. Akun superadmin siap digunakan. Karena dibuat lewat cara ini, akun akan otomatis diwajibkan mengganti password saat login pertama kali (lihat bagian 3.2).

Perintah yang sama juga dipakai untuk membuat akun Admin/PMO (Pelaksana Monitoring dan Operasional) secara manual di server jika suatu saat diperlukan, tapi cara yang lebih umum untuk kebutuhan sehari-hari adalah lewat portal Manajemen Akun (lihat bagian 3).

---

## 3. Portal Manajemen Akun (Superadmin)

Buka `https://adminsigapkopdes.duckdns.org`.

### 3.1 Login

Masukkan username dan password yang sudah dibuat di bagian 2, lalu klik **Masuk**. Portal ini menolak login dari akun yang bukan superadmin — akun Admin/PMO (Pelaksana Monitoring dan Operasional) harus login lewat dashboard utama, bukan di sini.

### 3.2 Ganti Password Pertama Kali

Karena akun superadmin dibuat dengan password sementara, sistem akan langsung meminta penggantian password sebelum bisa melanjutkan. Isi password lama, password baru (minimal 8 karakter, harus berbeda dari yang lama), dan ulangi password baru, lalu simpan.

### 3.3 Membuat Akun Admin atau PMO (Pelaksana Monitoring dan Operasional)

Di halaman **Manajemen Akun**, klik tombol **Tambah Akun**. Isi:

- **Username** — nama login untuk akun ini.
- **Password awal** — minimal 8 karakter. Pemilik akun akan diwajibkan menggantinya sendiri saat login pertama kali.
- **Role**:
  - **Pemerintah Pusat (Admin)** — otomatis mendapat akses ke semua wilayah, tidak perlu memilih wilayah tambahan.
  - **PMO (Pelaksana Monitoring dan Operasional)** — wajib memilih minimal satu kabupaten/kota dari daftar yang muncul. Akun ini hanya akan bisa melihat data koperasi di wilayah yang dipilih.

Klik **Simpan**. Akun baru langsung bisa dipakai untuk login di dashboard utama.

### 3.4 Mengelola Akun yang Sudah Ada

Tabel di halaman ini menampilkan semua akun (kecuali superadmin) beserta role, cakupan wilayah, dan status password-nya. Untuk tiap akun tersedia tiga aksi:

- **Edit** — mengubah role dan/atau cakupan wilayah akun.
- **Reset Password** — mengatur ulang password akun tersebut (misalnya karena pemiliknya lupa password). Setelah di-reset, pemilik akun akan diwajibkan mengganti password itu lagi saat login berikutnya.
- **Hapus** — menghapus akun secara permanen, dengan konfirmasi terlebih dahulu.

Akun superadmin sendiri tidak bisa diubah atau dihapus lewat portal ini — itu memang dibatasi karena sistem hanya boleh punya satu superadmin.

### 3.5 Mengatur Provider dan API Key AI Insight

Masih di halaman yang sama, terdapat kartu **AI Insight — Provider & API Key**. Ini mengatur mesin AI yang dipakai untuk menghasilkan narasi dan rekomendasi di halaman Detail Koperasi (lihat bagian 4.4).

1. **Provider AI aktif** — pilih salah satu (mis. Anthropic Claude, Google Gemini, atau Ollama Cloud), lalu klik **Ganti Provider**.
2. **Id model** (opsional) — id model spesifik dari provider yang dipilih. Bisa diisi lebih dari satu id dipisah koma sebagai cadangan berurutan (kalau model pertama gagal, sistem otomatis mencoba yang berikutnya). Kalau dikosongkan, sistem memakai model default.
3. **API Key** — masukkan API key dari provider yang dipilih, lalu klik **Simpan API Key**.

Perubahan di sini berlaku langsung tanpa perlu me-restart server, dan tersimpan permanen.

---

## 4. Dashboard Utama (Admin/PMO (Pelaksana Monitoring dan Operasional))

Buka `https://sigapkopdes.duckdns.org`.

### 4.1 Login

Masukkan username dan password. Untuk akun yang baru dibuat oleh superadmin, gunakan password sementara yang diberikan — sistem akan meminta penggantian password sebelum masuk ke dashboard (sama seperti bagian 3.2).

Setelah berhasil login, tampil sidebar di sisi kiri berisi menu navigasi, dan area konten utama di sisi kanan.

### 4.2 Halaman Ringkasan

Halaman pertama yang tampil setelah login. Menampilkan:

- **Kartu statistik**: rata-rata skor komposit seluruh koperasi (dalam cakupan akun Anda), jumlah koperasi per kategori (Sehat/Waspada/Kritis), dan jumlah notifikasi yang belum ditindaklanjuti.
- **Peta Sebaran Koperasi**: peta interaktif Indonesia. Klik sebuah provinsi untuk melihat rincian per kabupaten/kota, lalu klik kabupaten/kota untuk melihat titik tiap koperasi. Warna tiap titik menunjukkan kategori kelayakan (hijau = Sehat, kuning = Waspada, merah = Kritis).
- **Tabel notifikasi terbaru** yang belum ditindaklanjuti, dengan tautan langsung ke detail koperasi terkait.

### 4.3 Halaman Daftar Koperasi

Menampilkan seluruh koperasi dalam cakupan akun Anda dalam bentuk tabel, dengan kolom skor komposit, kategori, dan persentase risiko kritis 3 bulan ke depan. Tersedia filter berdasarkan kategori dan wilayah di bagian atas tabel. Klik nama koperasi untuk membuka halaman detailnya.

### 4.4 Halaman Detail Koperasi

Diakses dengan klik nama koperasi dari halaman Ringkasan atau Daftar Koperasi. Berisi:

- **Skor Kelayakan Komposit** — angka 0–100 dengan kategori (Sehat/Waspada/Kritis), perubahan dari bulan lalu, dan persentase proyeksi risiko Kritis 3 bulan ke depan.
- **Profil Koperasi** — jenis usaha, jumlah anggota, status operasional, PMO (Pelaksana Monitoring dan Operasional) penanggung jawab, status kemajuan desa (IDM), mata pencaharian dominan wilayah, dan akses ke pusat perdagangan.
- **Tren Skor Kelayakan** — grafik garis skor komposit dan tiga sub-skornya (transaksi, stok, pelaporan) selama beberapa bulan terakhir.
- **AI Insight & Rekomendasi** — dihasilkan otomatis saat halaman dibuka (butuh beberapa detik). Berisi narasi kondisi koperasi, rekomendasi tindakan untuk PMO (Pelaksana Monitoring dan Operasional), ide produk/jasa prioritas, ide kampanye promosi, dan ide program non-produk (pelatihan, kemitraan, dst).

### 4.5 Halaman Notifikasi

Menampilkan seluruh notifikasi otomatis dari sistem — diterbitkan saat skor komposit sebuah koperasi turun signifikan, atau saat koperasi masuk kategori Kritis. Tersedia filter berdasarkan status tindak lanjut.

### 4.6 Halaman Kriteria & Metodologi

Halaman referensi yang menjelaskan secara lengkap arti tiap angka dan kategori yang dipakai di seluruh dashboard: ambang kategori Sehat/Waspada/Kritis, cara perhitungan skor komposit dan bobot tiap sub-skor, cara kerja model prediksi risiko, aturan penerbitan notifikasi otomatis, dan penjelasan status kemajuan desa (IDM). Halaman ini berguna untuk memastikan tidak ada angka yang perlu ditebak-tebak artinya.

### 4.7 Ganti Password dan Keluar

Kedua aksi ini tersedia di bagian bawah sidebar, di semua halaman:

- **Ganti Password** — untuk mengganti password akun sendiri kapan saja, tidak harus menunggu diwajibkan sistem.
- **Keluar** — mengakhiri sesi login dan kembali ke halaman login.

---

## 5. Ringkasan Alur Penggunaan

1. Superadmin dibuat sekali di server (bagian 2).
2. Superadmin login ke portal Manajemen Akun, ganti password pertama kali (bagian 3.1–3.2).
3. Superadmin membuat akun Admin dan/atau PMO (Pelaksana Monitoring dan Operasional) sesuai kebutuhan, serta mengatur provider AI Insight (bagian 3.3–3.5).
4. Admin/PMO (Pelaksana Monitoring dan Operasional) login ke dashboard utama, ganti password pertama kali (bagian 4.1).
5. Admin/PMO (Pelaksana Monitoring dan Operasional) memantau kondisi koperasi lewat halaman Ringkasan, menelusuri detail lewat Daftar Koperasi, menindaklanjuti Notifikasi, dan merujuk ke Kriteria & Metodologi bila perlu memastikan arti suatu angka.
