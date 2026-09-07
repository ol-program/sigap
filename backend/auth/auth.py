"""
SIGAP Kopdes - Autentikasi & Otorisasi Berbasis Wilayah
==========================================================
Ditambahkan setelah step 7 karena dashboard menampilkan data sensitif
(kondisi finansial tiap koperasi di banyak wilayah) dan step 8 akan
mem-publikasikan API ini ke internet -- tanpa lapisan ini, siapa pun yang
tahu URL bisa melihat seluruh data. Lihat README bagian "Autentikasi &
Otorisasi" untuk konteks lengkap kenapa ini ditambahkan (bukan cuma
prinsip abstrak, tapi celah nyata begitu step 8 jalan).

Desain:
  - users disimpan di auth.db, TERPISAH dari sigap_kopdes.db -- supaya akun
    tidak ikut terhapus tiap kali generate_data.py menulis ulang database
    data (lihat write_sqlite() di generate_data.py yang hapus total file DB).
  - password di-hash dengan bcrypt (tidak pernah disimpan/di-log plain text).
  - sesi berbasis JWT (stateless, tanpa tabel sesi) -- payload berisi
    username, role, dan scope wilayah supaya endpoint bisa memfilter tanpa
    query balik ke tabel users tiap request.
  - role "admin" -> scope kosong berarti akses semua wilayah.
    role "pmo"   -> scope berisi daftar kode_wilayah yang boleh dilihat;
    filter diterapkan di lapisan SQL (WHERE kode_wilayah IN (...)), bukan
    disaring belakangan di Python, supaya data di luar scope tidak pernah
    ikut terbaca dari DB sama sekali.
  - JWT_SECRET WAJIB dari environment variable -- sengaja tidak ada default
    tertanam di kode (secret hardcoded adalah salah satu penyebab kebocoran
    paling umum). Aplikasi menolak start kalau env var ini kosong.
  - Rate limit percobaan login sederhana (in-memory, per username) untuk
    memperlambat brute-force -- cukup untuk single-process demo, tapi kalau
    dijalankan multi-worker/multi-instance di step 8, pindahkan ke Redis
    atau layanan rate-limit terkelola (in-memory tidak dibagi antar proses).
"""
import os
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

HERE = os.path.dirname(os.path.abspath(__file__))
AUTH_DB_PATH = os.path.join(HERE, "auth.db")
DATA_DB_PATH = os.path.join(HERE, "..", "data", "output", "sigap_kopdes.db")

JWT_SECRET = os.environ.get("JWT_SECRET")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 8

MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCKOUT_SECONDS = 300  # 5 menit

_login_attempts = {}  # username -> [(timestamp, sukses_bool), ...] -- in-memory, lihat catatan di docstring

bearer_scheme = HTTPBearer(auto_error=False)


def _require_secret():
    if not JWT_SECRET:
        raise RuntimeError(
            "JWT_SECRET belum di-set di environment. Jangan jalankan API tanpa ini "
            "(lihat README bagian Autentikasi) -- export JWT_SECRET=<random-panjang>."
        )


def get_auth_conn():
    conn = sqlite3.connect(AUTH_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_auth_db():
    conn = get_auth_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'pmo', 'superadmin')),
            kode_wilayah_scope TEXT NOT NULL DEFAULT '',
            must_change_password INTEGER NOT NULL DEFAULT 0
        )
    """)
    # Migrasi untuk auth.db lama yang dibuat sebelum kolom ini ada -- SQLite
    # tidak punya "ADD COLUMN IF NOT EXISTS", jadi dicek manual lewat
    # PRAGMA. Default 0 supaya akun yang sudah ada (dibuat sebelum fitur
    # paksa-ganti-password ini) TIDAK mendadak terkunci keluar -- hanya akun
    # baru (create_user_record) atau yang di-reset (admin_reset_password)
    # yang dipaksa ganti password.
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
    if "must_change_password" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0")
    # Migrasi CHECK constraint lama (role IN ('admin','pmo'), tanpa
    # 'superadmin') -- SQLite tidak bisa ALTER sebuah CHECK constraint
    # langsung, jadi tabel di-rebuild (rename -> create baru -> copy data ->
    # drop lama) kalau constraint lama masih terpasang. Dicek dari teks SQL
    # tabel di sqlite_master supaya idempoten (aman dijalankan berkali-kali
    # tiap startup, cuma benar-benar rebuild sekali).
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='users'").fetchone()
    if row and "'superadmin'" not in row["sql"]:
        conn.executescript("""
            ALTER TABLE users RENAME TO users_old_migrasi_superadmin;
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('admin', 'pmo', 'superadmin')),
                kode_wilayah_scope TEXT NOT NULL DEFAULT '',
                must_change_password INTEGER NOT NULL DEFAULT 0
            );
            INSERT INTO users (id, username, password_hash, role, kode_wilayah_scope, must_change_password)
                SELECT id, username, password_hash, role, kode_wilayah_scope, must_change_password
                FROM users_old_migrasi_superadmin;
            DROP TABLE users_old_migrasi_superadmin;
        """)
    conn.commit()
    conn.close()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def get_user(username: str) -> Optional[sqlite3.Row]:
    conn = get_auth_conn()
    try:
        return conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    finally:
        conn.close()


def _is_locked_out(username: str) -> bool:
    now = time.time()
    attempts = [t for t in _login_attempts.get(username, []) if now - t < LOGIN_LOCKOUT_SECONDS]
    _login_attempts[username] = attempts
    return len(attempts) >= MAX_LOGIN_ATTEMPTS


def _record_failed_attempt(username: str):
    _login_attempts.setdefault(username, []).append(time.time())


def authenticate(username: str, password: str) -> sqlite3.Row:
    """Verifikasi kredensial. Melempar HTTPException 401/429 kalau gagal --
    pesan error SENGAJA generik ("username atau password salah") supaya
    tidak membocorkan apakah username tertentu terdaftar (mencegah user
    enumeration)."""
    if _is_locked_out(username):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Terlalu banyak percobaan gagal. Coba lagi setelah {LOGIN_LOCKOUT_SECONDS // 60} menit.",
        )
    user = get_user(username)
    if user is None or not verify_password(password, user["password_hash"]):
        _record_failed_attempt(username)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Username atau password salah.")
    return user


def create_access_token(user: sqlite3.Row) -> str:
    _require_secret()
    scope = [s for s in user["kode_wilayah_scope"].split(",") if s]
    payload = {
        "sub": user["username"],
        "role": user["role"],
        "scope": scope,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


class CurrentUser:
    def __init__(self, username, role, scope):
        self.username = username
        self.role = role
        self.scope = scope  # list kode_wilayah; kosong & role=admin berarti akses semua

    @property
    def is_admin(self):
        return self.role == "admin"

    @property
    def is_superadmin(self):
        return self.role == "superadmin"


def get_current_user(creds: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> CurrentUser:
    _require_secret()
    if creds is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Belum login -- sertakan header Authorization: Bearer <token>.")
    try:
        payload = jwt.decode(creds.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesi kedaluwarsa, silakan login ulang.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token tidak valid.")
    return CurrentUser(payload["sub"], payload["role"], payload.get("scope", []))


def scope_clause(user: CurrentUser, alias: str):
    """Potongan SQL "AND {alias}.kode_wilayah IN (...)" untuk role pmo, string
    kosong untuk admin (tanpa pembatasan). Dipakai di SEMUA endpoint yang
    membaca data berbasis wilayah -- filter diterapkan di SQL, bukan Python,
    supaya baris di luar scope tidak pernah keluar dari database sama sekali.
    PMO tanpa scope (kode_wilayah_scope kosong) sengaja tidak melihat apa pun
    (WHERE 1=0) daripada default ke "lihat semua" -- fail closed, bukan fail open."""
    if user.is_admin:
        return "", []
    if not user.scope:
        return " AND 1=0", []
    placeholders = ",".join(["?"] * len(user.scope))
    return f" AND {alias}.kode_wilayah IN ({placeholders})", list(user.scope)


def get_active_user(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """Sama seperti get_current_user, TAPI menolak (403) kalau akun masih
    wajib ganti password (must_change_password), dan dicek FRESH dari
    auth.db tiap request -- BUKAN dari payload JWT -- supaya dua hal ini
    langsung berlaku pada request berikutnya, tanpa menunggu token lama
    (berlaku 8 jam) kedaluwarsa:
      1. admin reset password paksa akun yang sedang login di tab lain
      2. admin hapus akun yang sedang login (token lama technically masih
         valid secara kriptografis sampai exp, tapi akunnya sudah tidak ada)
    Dipakai di semua endpoint DATA. Sengaja TIDAK dipakai di
    /auth/change-password -- endpoint itu justru harus tetap bisa dipanggil
    justru SAAT must_change_password true (supaya user bisa keluar dari
    kondisi itu)."""
    row = get_user(user.username)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Akun tidak ditemukan atau sudah dihapus, silakan login ulang.",
        )
    if row["must_change_password"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "MUST_CHANGE_PASSWORD", "message": "Anda harus mengganti password sebelum melanjutkan."},
        )
    return user


def get_superadmin_user(user: CurrentUser = Depends(get_active_user)) -> CurrentUser:
    """Dipakai di endpoint manajemen akun (/admin/users/*) -- menolak (403)
    kalau role BUKAN superadmin. Sengaja dipisah dari role "admin" (yang
    cuma berarti akses semua wilayah DATA koperasi) -- role "admin" bisa
    dipakai lebih dari satu orang untuk kebutuhan lihat-data, dan mereka
    TIDAK otomatis boleh membuat/hapus akun atau reset password orang lain.
    superadmin adalah role terpisah yang HANYA punya wewenang manajemen
    akun, dan sengaja tidak lihat data koperasi apa pun (lihat scope_clause
    -- superadmin bukan is_admin, dan scope-nya selalu kosong, jadi fail
    closed di semua endpoint data). Membungkus get_active_user (bukan
    get_current_user langsung) supaya superadmin dengan must_change_password
    aktif juga wajib beres-beres password sendiri dulu sebelum bisa kelola
    akun lain."""
    if not user.is_superadmin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Hanya superadmin yang boleh mengakses ini.")
    return user


def resolve_kabupaten(nama_kabupaten: str) -> list:
    """Semua kode_wilayah dalam satu kabupaten/kota, dibaca dari
    sigap_kopdes.db -- dipakai baik oleh CLI (create_user.py) maupun endpoint
    admin (api/main.py) supaya scope PMO selalu di-resolve dengan cara yang
    SAMA (satu sumber kebenaran), bukan dua implementasi yang bisa diam-diam
    menyimpang seiring waktu."""
    if not os.path.exists(DATA_DB_PATH):
        raise ValueError(f"sigap_kopdes.db tidak ditemukan di {DATA_DB_PATH} -- jalankan step 2 dulu.")
    conn = sqlite3.connect(DATA_DB_PATH)
    try:
        rows = conn.execute(
            "SELECT kode_wilayah FROM wilayah WHERE kabupaten_kota = ?", (nama_kabupaten,)
        ).fetchall()
    finally:
        conn.close()
    if not rows:
        raise ValueError(f"Tidak ada wilayah dengan kabupaten_kota = '{nama_kabupaten}'.")
    return [r[0] for r in rows]


def resolve_scope(kabupaten_list: list) -> list:
    scope = []
    for nama in kabupaten_list:
        scope.extend(resolve_kabupaten(nama))
    return scope


def list_users() -> list:
    conn = get_auth_conn()
    try:
        rows = conn.execute(
            "SELECT id, username, role, kode_wilayah_scope, must_change_password FROM users ORDER BY username"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def create_user_record(username: str, password: str, role: str, scope: list, must_change_password: bool = True):
    """must_change_password default True -- akun baru selalu dibuat dengan
    password yang DIKETAHUI admin (bukan pemiliknya), jadi pemilik akun WAJIB
    menggantinya sebelum bisa memakai dashboard."""
    if len(password) < 8:
        raise ValueError("Password minimal 8 karakter.")
    conn = get_auth_conn()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash, role, kode_wilayah_scope, must_change_password) "
            "VALUES (?, ?, ?, ?, ?)",
            (username, hash_password(password), role, ",".join(scope), 1 if must_change_password else 0),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        raise ValueError(f"Username '{username}' sudah dipakai.")
    finally:
        conn.close()


def update_user_scope(username: str, role: str, scope: list):
    conn = get_auth_conn()
    try:
        cur = conn.execute(
            "UPDATE users SET role = ?, kode_wilayah_scope = ? WHERE username = ?",
            (role, ",".join(scope), username),
        )
        conn.commit()
        if cur.rowcount == 0:
            raise ValueError(f"Akun '{username}' tidak ditemukan.")
    finally:
        conn.close()


def delete_user_record(username: str):
    conn = get_auth_conn()
    try:
        cur = conn.execute("DELETE FROM users WHERE username = ?", (username,))
        conn.commit()
        if cur.rowcount == 0:
            raise ValueError(f"Akun '{username}' tidak ditemukan.")
    finally:
        conn.close()


def admin_reset_password(username: str, new_password: str):
    """Dipakai admin buat reset password akun lain -- SELALU menyalakan
    kembali must_change_password (beda dari self_change_password), karena
    password baru ini diketahui admin, bukan rahasia milik pemilik akun."""
    if len(new_password) < 8:
        raise ValueError("Password minimal 8 karakter.")
    conn = get_auth_conn()
    try:
        cur = conn.execute(
            "UPDATE users SET password_hash = ?, must_change_password = 1 WHERE username = ?",
            (hash_password(new_password), username),
        )
        conn.commit()
        if cur.rowcount == 0:
            raise ValueError(f"Akun '{username}' tidak ditemukan.")
    finally:
        conn.close()


def self_change_password(user_row: sqlite3.Row, old_password: str, new_password: str):
    """Dipakai user sendiri (lewat POST /auth/change-password) -- BEDA dari
    admin_reset_password: butuh password lama yang benar, dan sukses di sini
    MEMATIKAN must_change_password (bukan menyalakannya) karena password baru
    ini sekarang rahasia milik pemiliknya sendiri, admin tidak tahu."""
    if not verify_password(old_password, user_row["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Password lama salah.")
    if len(new_password) < 8:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Password baru minimal 8 karakter.")
    if verify_password(new_password, user_row["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password baru harus berbeda dari password lama.",
        )
    conn = get_auth_conn()
    try:
        conn.execute(
            "UPDATE users SET password_hash = ?, must_change_password = 0 WHERE username = ?",
            (hash_password(new_password), user_row["username"]),
        )
        conn.commit()
    finally:
        conn.close()
