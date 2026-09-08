# Deployment VPS — checklist provisioning awal

Konfigurasi di folder ini (systemd, nginx, `deploy.sh`) dipakai berulang oleh
CI/CD (`.github/workflows/deploy.yml`), tapi langkah **provisioning pertama
kali** di bawah ini manual — jalankan sekali per VPS.

**VPS ini spesifik:** Ubuntu 20.04 LTS (Focal), ~1GB RAM, akses `root`,
IP `109.105.194.204`. Repo: https://github.com/ol-program/sigap (publik).

**Kenapa Python 3.12 di server ini dipasang lewat `uv`, bukan deadsnakes PPA
seperti draf awal (beda juga dari instruksi dev lokal di README utama):**
PPA deadsnakes ternyata **sudah kosong untuk Focal** (indeks paketnya 0 byte
-- di-diverifikasi langsung dari `InRelease` PPA-nya, bukan asumsi --
kemungkinan dihentikan setelah Focal EOL Mei 2025). `google-genai` (provider
Gemini, dipakai project ini) butuh Python **>=3.10**, dan Focal cuma punya
3.8 di apt default. Solusinya: [uv](https://docs.astral.sh/uv/) (Astral) --
binary statis, tidak perlu PPA/kompilasi, dan Python-nya prebuilt (~2 detik
install, bukan 15-30 menit kompilasi dari source yang berat untuk RAM 1GB
ini). Kalau nanti provider dibalik ke `AI_PROVIDER=anthropic` (tidak butuh
3.10+), venv `.venv312` ini tetap kompatibel -- tidak perlu diganti lagi.

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

# python 3.12 lewat uv (lihat catatan di atas soal deadsnakes vs uv)
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env
uv python install 3.12

# JEBAKAN PERMISSION: `uv python install` sebagai root nyimpen Python-nya di
# /root/.local/share/uv/python/... -- direktori /root sendiri permission-nya
# 700 (cuma root yang bisa traverse ke situ SAMA SEKALI, termasuk symlink di
# ~/.local/bin/python3.12 yang mengarah balik ke sana). Backend jalan sebagai
# `www-data` (lihat systemd unit), BUKAN root -- jadi kalau venv dibuat
# langsung dari `~/.local/bin/python3.12`, service akan gagal start dengan
# "Permission denied" spawning .venv312/bin/python (venv-nya juga cuma
# symlink balik ke /root). Pernah kejadian PERSIS ini saat deploy pertama.
# Fix: copy Python-nya (DEREFERENCE symlink dengan -L, bukan cuma copy
# symlink-nya) ke lokasi yang bisa ditraverse semua user, baru venv dibuat
# dari situ:
mkdir -p /opt/uv-python
SRC=$(dirname "$(dirname "$(readlink -f "$HOME/.local/bin/python3.12")")")   # ikut versi patch apa pun yang ke-install
cp -aL "$SRC" /opt/uv-python/cpython-3.12
chmod -R o+rX /opt/uv-python
sudo -u www-data /opt/uv-python/cpython-3.12/bin/python3.12 --version   # harus sukses print versi, bukan Permission denied

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
/opt/uv-python/cpython-3.12/bin/python3.12 -m venv .venv312   # BUKAN ~/.local/bin/python3.12 -- lihat jebakan permission /root di langkah 1
.venv312/bin/pip install -r requirements.txt google-genai ollama
chown -R www-data:www-data .venv312   # service jalan sebagai www-data, lihat systemd unit

cp /opt/sigap-kopdes/deploy/systemd/sigap-kopdes-backend.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now sigap-kopdes-backend
systemctl status sigap-kopdes-backend --no-pager
```

**Catatan penting soal permission:** `git clone` di langkah 2 bikin semua
file dimiliki `root`, tapi service jalan sebagai `www-data` (lihat `User=`
di systemd unit, praktik baik -- backend TIDAK jalan sebagai root). Kalau
lupa `chown` di atas, service akan crash-restart terus dengan error
`sqlite3.OperationalError: unable to open database file` karena `www-data`
tidak bisa tulis `auth/auth.db`. `chown -R www-data:www-data` juga perlu
dijalankan untuk `backend/auth/` dan `backend/data/output/` (bukan cuma
`.venv312/`) -- lihat `ReadWritePaths` di systemd unit untuk daftar lengkap
folder yang perlu bisa ditulis `www-data`:
```bash
chown -R www-data:www-data /opt/sigap-kopdes/backend/auth /opt/sigap-kopdes/backend/data/output
```

## 6. Akun pertama (superadmin wajib lewat CLI, lihat README)

```bash
cd /opt/sigap-kopdes/backend
export JWT_SECRET=$(grep JWT_SECRET .env.production | cut -d= -f2)
.venv312/bin/python auth/create_user.py --username superadmin --role superadmin
.venv312/bin/python auth/create_user.py --username admin --role admin
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
