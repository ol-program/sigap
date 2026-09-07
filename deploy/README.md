# Deployment VPS — checklist provisioning awal

Konfigurasi di folder ini (systemd, nginx, `deploy.sh`) dipakai berulang oleh
CI/CD (`.github/workflows/deploy.yml`), tapi langkah **provisioning pertama
kali** di bawah ini manual — jalankan sekali per VPS.

## 1. Siapkan server

```bash
# di VPS, sebagai root/sudo:
apt update && apt install -y nginx git python3.12 python3.12-venv nodejs npm certbot python3-certbot-nginx
adduser --system --group --home /opt/sigap-kopdes deploy   # atau user non-root yang sudah ada
mkdir -p /opt/sigap-kopdes && chown deploy:deploy /opt/sigap-kopdes
```

## 2. Clone repo & setup key deploy CI/CD

```bash
su - deploy
git clone <URL_REPO_GITHUB> /opt/sigap-kopdes
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/deploy_key -N ""
cat ~/.ssh/deploy_key.pub >> ~/.ssh/authorized_keys
cat ~/.ssh/deploy_key   # isi private key ini ke secret VPS_SSH_KEY di GitHub
```

Tambahkan di GitHub repo → Settings → Secrets and variables → Actions:
`VPS_HOST`, `VPS_USER` (`deploy`), `VPS_SSH_KEY` (isi `deploy_key` di atas).

## 3. Kredensial aplikasi (TIDAK lewat git/CI, copy manual sekali)

```bash
# dari mesin lokal:
scp backend/.env.production deploy@<VPS_HOST>:/opt/sigap-kopdes/backend/.env.production
scp frontend/.env.production deploy@<VPS_HOST>:/opt/sigap-kopdes/frontend/.env.production
scp frontend-admin/.env.production deploy@<VPS_HOST>:/opt/sigap-kopdes/frontend-admin/.env.production
```

Lalu di VPS, isi `ANTHROPIC_API_KEY`/`GEMINI_API_KEY` **langsung di file**
(`nano /opt/sigap-kopdes/backend/.env.production`) — jangan pernah lewat
chat/CI. Isi juga `CORS_ORIGINS` di file yang sama dan `VITE_API_BASE_URL`
di kedua `.env.production` frontend dengan domain asli (lihat langkah 4).

## 4. Domain (atau sslip.io kalau belum ada domain)

Ganti `REPLACE_WITH_*_DOMAIN` di `deploy/nginx/*.conf` dengan domain asli.
Kalau belum ada domain, pakai [sslip.io](https://sslip.io) (resolve otomatis
ke IP tanpa perlu beli domain, dan tetap bisa dapat SSL asli lewat certbot):
IP `203.0.113.10` → `dash.203-0-113-10.sslip.io`, `admin.203-0-113-10.sslip.io`,
`api.203-0-113-10.sslip.io`.

```bash
sudo cp deploy/nginx/*.conf /etc/nginx/sites-available/
sudo ln -s /etc/nginx/sites-available/dashboard.conf /etc/nginx/sites-enabled/
sudo ln -s /etc/nginx/sites-available/admin.conf /etc/nginx/sites-enabled/
sudo ln -s /etc/nginx/sites-available/api.conf /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d <dash-domain> -d <admin-domain> -d <api-domain>
```

## 5. Backend service

```bash
sudo cp deploy/systemd/sigap-kopdes-backend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now sigap-kopdes-backend
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

Setelah ini, tiap push ke `main`/`master` yang lolos CI otomatis trigger
`deploy.sh` lewat GitHub Actions (`.github/workflows/deploy.yml`).

## Backup

`backend/auth/auth.db` **tidak** ikut redeploy/regenerasi data — backup
terpisah secara berkala (mis. cron `sqlite3 auth.db ".backup ..."` ke
storage lain), lihat catatan di README bagian "Rencana deployment".
