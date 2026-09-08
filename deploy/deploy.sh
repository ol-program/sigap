#!/usr/bin/env bash
# Dijalankan DI VPS (lewat SSH dari .github/workflows/deploy.yml, atau manual).
# Asumsi: repo sudah di-clone sekali ke /opt/sigap-kopdes, backend/.env.production
# sudah ada di sana (di-deploy manual, TIDAK lewat git -- lihat catatan
# di .github/workflows/deploy.yml dan README bagian "Rencana deployment"),
# dan systemd service + nginx (lihat deploy/systemd, deploy/nginx) sudah
# di-install sekali secara manual saat provisioning awal.
set -euo pipefail

# SELURUH isi deploy asli dibungkus fungsi main() yang dipanggil di baris
# PALING BAWAH file ini -- SENGAJA, bukan gaya penulisan semata. Bug nyata
# yang ditemukan: skrip ini `git pull` DIRINYA SENDIRI di baris pertama
# (deploy.sh ada di repo yang di-pull), lalu bash MELANJUTKAN membaca file
# yang SAMA di disk untuk baris-baris berikutnya berdasarkan OFFSET BYTE --
# begitu commit yang di-pull mengubah PANJANG deploy.sh (mis. menambah kata
# di baris pip install), sisa skrip yang dieksekusi jadi CAMPUR ANTARA versi
# lama & baru sejak titik itu (bergantung ukuran perubahan), TANPA error apa
# pun -- kejadian nyata: baris `pip install ... ollama` yang baru ditambah
# ternyata dieksekusi sebagai baris LAMA (tanpa `ollama`) walau `git log` &
# commit yang ter-checkout sudah benar, karena bash sudah kadung membaca
# offset lama untuk baris itu. Fix standar untuk self-modifying script: bash
# membaca SELURUH definisi fungsi ke memori SEBELUM menjalankan apa pun di
# dalamnya, jadi bungkus semua langkah dalam satu fungsi & panggil fungsi itu
# di baris terakhir -- git pull di baris pertama BOLEH mengubah file di disk,
# tapi eksekusi yang sedang berjalan sudah tidak lagi membaca ulang dari disk.
main() {
  APP_DIR=/opt/sigap-kopdes
  cd "$APP_DIR"

  echo "==> git pull"
  git pull --ff-only origin main

  echo "==> backend: install deps (venv python3.12 via uv, sesuai deploy/README.md -- google-genai butuh 3.10+)"
  cd "$APP_DIR/backend"
  .venv312/bin/pip install -q -r requirements.txt google-genai ollama

  echo "==> frontend: build"
  cd "$APP_DIR/frontend"
  npm ci --silent
  npm run build --silent

  echo "==> frontend-admin: build"
  cd "$APP_DIR/frontend-admin"
  npm ci --silent
  npm run build --silent

  echo "==> restart backend service"
  systemctl restart sigap-kopdes-backend
  systemctl --no-pager --lines=0 status sigap-kopdes-backend

  echo "==> reload nginx (serve dist/ baru)"
  nginx -t
  systemctl reload nginx

  echo "==> selesai"
}

main "$@"
