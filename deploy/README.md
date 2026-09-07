# Deployment VPS — checklist provisioning awal

Konfigurasi di folder ini (systemd, nginx, `deploy.sh`) dipakai berulang oleh
CI/CD (`.github/workflows/deploy.yml`), tapi langkah **provisioning pertama
kali** di bawah ini manual — jalankan sekali per VPS.

**VPS ini spesifik:** Ubuntu 20.04 LTS (Focal), ~1GB RAM, akses `root`,
IP `109.105.194.204`. Repo: https://github.com/ol-program/sigap (publik).

**Kenapa bukan Python 3.12 di server (beda dari instruksi dev lokal di
README utama):** rencana awal pakai `python3.12` dari PPA deadsnakes, TAPI
PPA itu ternyata **sudah kosong untuk Focal** (indeks paketnya 0 byte --
di-diverifikasi langsung dari `InRelease` PPA-nya, bukan asumsi -- kemungkinan
dihentikan setelah Focal EOL Mei 2025). Solusinya: backend di VPS ini pakai
Python **3.8 bawaan sistem** + `.venv` biasa -- ini cukup karena
`backend/.env.production` sudah di-set `AI_PROVIDER=anthropic` (default
project), dan kebutuhan Python 3.10+ di README utama itu SPESIFIK untuk
`google-genai` (provider Gemini) yang tidak dipakai di deployment ini. Kalau
nanti mau pindah ke Gemini di server ini, baru perlu Python 3.10+ lewat cara
lain (kompilasi dari source, atau `uv python install`) -- BUKAN deadsnakes.

**RAM ~1GB, swapfile 2GB dibuat DULU** sebelum instal apa pun supaya proses
`npm run build` (2 frontend React) tidak ke-OOM-kill.

**Catatan keamanan:** provisioning & deploy di sini pakai `root` langsung
(sesuai akses yang tersedia), bukan user non-root berhak-terbatas seperti
draf awal dokumen ini. Ini pragmatis untuk keperluan demo datathon dengan
waktu terbatas, tapi berarti key CI/CD (`VPS_SSH_KEY` di GitHub) punya akses
root penuh ke server -- kalau nanti mau dikeraskan, buat user `deploy` baru
dengan sudoers terbatas ke `systemctl restart sigap-kopdes-backend` dan
`nginx -s reload` saja, lalu pindahkan `VPS_SSH_KEY` ke situ.

## 1. Siapkan server

```bash
# di VPS, sebagai root:
apt update && apt upgrade -y

# swap 2GB dulu -- RAM cuma ~1GB, npm run build butuh headroom
fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile
swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab

# python venv + pip (python3.8 bawaan Focal, lihat catatan di atas soal 3.12)
apt install -y python3-venv python3-pip

# node 20 LTS -- Focal punya nodejs versi lama di apt default, pakai NodeSource
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt install -y nodejs

# nginx + git
apt install -y nginx git

# certbot -- pakai snap (lebih reliable di Ubuntu lama daripada certbot apt)
apt install -y snapd
snap install core && snap refresh core
snap install --classic certbot
ln -sf /snap/bin/certbot /usr/bin/certbot

# firewall dasar
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable
```

## 2. Clone repo & setup key deploy CI/CD

Repo publik, jadi VPS bisa `git clone` langsung lewat HTTPS tanpa perlu key
apa pun untuk baca. Key di bawah ini KHUSUS supaya GitHub Actions bisa SSH
**masuk** ke VPS untuk menjalankan `deploy.sh` (arah sebaliknya).

```bash
git clone https://github.com/ol-program/sigap.git /opt/sigap-kopdes

# key KHUSUS untuk GitHub Actions (terpisah dari key akses manual kita):
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/deploy_key -N ""
cat ~/.ssh/deploy_key.pub >> ~/.ssh/authorized_keys
cat ~/.ssh/deploy_key   # isi private key ini ke secret VPS_SSH_KEY di GitHub
```

Tambahkan di GitHub repo → Settings → Secrets and variables → Actions:
`VPS_HOST` (`109.105.194.204`), `VPS_USER` (`root`), `VPS_SSH_KEY` (isi `deploy_key` di atas).

## 3. Kredensial aplikasi (TIDAK lewat git/CI, copy manual sekali)

```bash
# dari mesin lokal:
scp backend/.env.production root@109.105.194.204:/opt/sigap-kopdes/backend/.env.production
scp frontend/.env.production root@109.105.194.204:/opt/sigap-kopdes/frontend/.env.production
scp frontend-admin/.env.production root@109.105.194.204:/opt/sigap-kopdes/frontend-admin/.env.production
```

Lalu di VPS, isi `ANTHROPIC_API_KEY`/`GEMINI_API_KEY` **langsung di file**
(`nano /opt/sigap-kopdes/backend/.env.production`) — jangan pernah lewat
chat/CI. `CORS_ORIGINS`/`VITE_API_BASE_URL` di file-file ini sudah diisi
domain sslip.io (lihat langkah 4), tinggal `ANTHROPIC_API_KEY` yang perlu
diisi manual.

## 4. Domain (sslip.io, karena belum ada domain asli)

IP VPS: `109.105.194.204` → domain sslip.io-nya:
- Dashboard: `dash.109-105-194-204.sslip.io`
- Portal superadmin: `admin.109-105-194-204.sslip.io`
- API: `api.109-105-194-204.sslip.io`

`server_name` di `deploy/nginx/*.conf` sudah diisi domain di atas. Kalau
nanti beli domain asli, tinggal ganti `server_name` di tiga file itu +
`CORS_ORIGINS`/`VITE_API_BASE_URL`, lalu `certbot --nginx` ulang untuk
domain baru.

```bash
cp /opt/sigap-kopdes/deploy/nginx/*.conf /etc/nginx/sites-available/
ln -sf /etc/nginx/sites-available/dashboard.conf /etc/nginx/sites-enabled/
ln -sf /etc/nginx/sites-available/admin.conf /etc/nginx/sites-enabled/
ln -sf /etc/nginx/sites-available/api.conf /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
certbot --nginx \
  -d dash.109-105-194-204.sslip.io \
  -d admin.109-105-194-204.sslip.io \
  -d api.109-105-194-204.sslip.io
```

## 5. Backend service

```bash
cd /opt/sigap-kopdes/backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

cp /opt/sigap-kopdes/deploy/systemd/sigap-kopdes-backend.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now sigap-kopdes-backend
systemctl status sigap-kopdes-backend --no-pager
```

## 6. Akun pertama (superadmin wajib lewat CLI, lihat README)

```bash
cd /opt/sigap-kopdes/backend
export JWT_SECRET=$(grep JWT_SECRET .env.production | cut -d= -f2)
.venv/bin/python auth/create_user.py --username superadmin --role superadmin
.venv/bin/python auth/create_user.py --username admin --role admin
```

## 7. Build awal frontend + jalankan deploy.sh

```bash
bash /opt/sigap-kopdes/deploy/deploy.sh
```

Setelah secrets CI/CD diisi (langkah 2), tiap push ke `main` yang lolos CI
otomatis trigger `deploy.sh` lewat GitHub Actions
(`.github/workflows/deploy.yml`).

## Backup

`backend/auth/auth.db` **tidak** ikut redeploy/regenerasi data — backup
terpisah secara berkala (mis. cron `sqlite3 auth.db ".backup ..."` ke
storage lain), lihat catatan di README bagian "Rencana deployment".
