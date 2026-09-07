#!/usr/bin/env bash
# Dijalankan DI VPS (lewat SSH dari .github/workflows/deploy.yml, atau manual).
# Asumsi: repo sudah di-clone sekali ke /opt/sigap-kopdes, backend/.env.production
# sudah ada di sana (di-deploy manual, TIDAK lewat git -- lihat catatan
# di .github/workflows/deploy.yml dan README bagian "Rencana deployment"),
# dan systemd service + nginx (lihat deploy/systemd, deploy/nginx) sudah
# di-install sekali secara manual saat provisioning awal.
set -euo pipefail

APP_DIR=/opt/sigap-kopdes
cd "$APP_DIR"

echo "==> git pull"
git pull --ff-only origin main

echo "==> backend: install deps (venv python3.8 sistem -- AI_PROVIDER=anthropic, lihat deploy/README.md)"
cd "$APP_DIR/backend"
.venv/bin/pip install -q -r requirements.txt

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
