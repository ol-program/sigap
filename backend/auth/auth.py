"""
SIGAP Kopdes - Autentikasi & Otorisasi Berbasis Wilayah

Desain:
  - users disimpan di auth.db, terpisah dari sigap_kopdes.db (yang ditulis
    ulang total tiap generate_data.py dijalankan).
  - password di-hash dengan bcrypt.
  - sesi berbasis JWT (stateless), payload berisi username/role/scope.
  - role "admin" -> scope kosong berarti akses semua wilayah; role "pmo" ->
    scope berisi kode_wilayah yang boleh dilihat, difilter di SQL (bukan
    Python) supaya data di luar scope tidak pernah terbaca dari DB.
  - JWT_SECRET wajib dari environment variable, tidak ada default tertanam.
  - Rate limit login in-memory per username -- tidak dibagi antar proses,
    perlu dipindah ke Redis kalau dijalankan multi-worker/multi-instance.
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

_login_attempts = {}  # username -> [timestamp, ...] percobaan gagal, in-memory

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
    # Migrasi untuk auth.db lama tanpa kolom ini -- SQLite tidak punya
    # "ADD COLUMN IF NOT EXISTS", dicek manual lewat PRAGMA.
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
    if "must_change_password" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0")
    # Migrasi CHECK constraint lama (tanpa 'superadmin') -- SQLite tidak bisa
    # ALTER CHECK constraint langsung, jadi tabel di-rebuild kalau perlu.
    # Idempoten: dicek dari teks SQL tabel di sqlite_master.
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
    """Verifikasi kredensial. Pesan error generik (tidak membedakan username
    tidak ada vs password salah) untuk mencegah user enumeration."""
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
    """Potongan SQL "AND {alias}.kode_wilayah IN (...)" untuk role pmo,
    string kosong untuk admin. PMO tanpa scope sengaja tidak melihat apa pun
    (WHERE 1=0) -- fail closed, bukan fail open."""
    if user.is_admin:
        return "", []
    if not user.scope:
        return " AND 1=0", []
    placeholders = ",".join(["?"] * len(user.scope))
    return f" AND {alias}.kode_wilayah IN ({placeholders})", list(user.scope)


def get_active_user(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """Seperti get_current_user, tapi menolak (403) akun dengan
    must_change_password aktif, dan dicek fresh dari auth.db tiap request
    (bukan dari payload JWT) supaya reset password/penghapusan akun
    langsung berlaku tanpa menunggu token lama kedaluwarsa. Sengaja tidak
    dipakai di /auth/change-password, yang harus tetap bisa dipanggil
    justru saat must_change_password true."""
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
    kalau role bukan superadmin. Role terpisah dari "admin" (yang cuma
    berarti akses semua wilayah data koperasi): superadmin hanya punya
    wewenang manajemen akun, dan fail closed di semua endpoint data
    (bukan is_admin, scope selalu kosong -- lihat scope_clause)."""
    if not user.is_superadmin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Hanya superadmin yang boleh mengakses ini.")
    return user


def resolve_kabupaten(nama_kabupaten: str) -> list:
    """Semua kode_wilayah dalam satu kabupaten/kota. Dipakai oleh CLI
    (create_user.py) dan endpoint admin supaya scope PMO di-resolve konsisten."""
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
    """must_change_password default True: password awal diketahui admin,
    jadi pemilik akun wajib menggantinya sebelum memakai dashboard."""
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
    """Reset password oleh admin -- selalu menyalakan kembali
    must_change_password, beda dari self_change_password."""
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
    """Ganti password sendiri -- butuh password lama yang benar, dan
    mematikan must_change_password (beda dari admin_reset_password)."""
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
