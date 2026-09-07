"""
SIGAP Kopdes - Backend API (Step 6)
======================================
FastAPI read-only yang menyajikan hasil tiga engine sebelumnya -- skor
kesehatan (step 3), prediksi risiko (step 4), AI insight (step 5) -- ke
dashboard React (step 7). API ini TIDAK menghitung apa pun sendiri, murni
query & serialisasi dari sigap_kopdes.db -- konsisten dengan prinsip di
step 3-5: satu sumber kebenaran angka, bukan dihitung ulang berbeda-beda
di tiap lapisan.

Kenapa baca SQLite langsung tiap request, bukan load ke memori sekali di
startup? Dataset prototipe ini kecil (< 1.000 baris skor_kesehatan) dan
sigap_kopdes.db diregenerasi lewat pipeline batch (step 2-5), bukan lewat
API ini -- jadi query langsung lebih sederhana daripada mengurus cache
invalidation, dengan biaya performa yang bisa diabaikan pada skala ini.

Tabel `ai_insight` (step 5) OPSIONAL: baru terisi kalau step 5 sudah
pernah dijalankan sungguhan (bukan --dry-run) dengan ANTHROPIC_API_KEY
milik Anda. Endpoint yang membacanya menoleransi tabel belum ada / baris
belum ada (mengembalikan null), bukan error 500 -- supaya API tetap bisa
dipakai untuk demo skor & prediksi walau step 5 belum dijalankan.

SEMUA endpoint data di bawah (kecuali "/" dan "/auth/login") butuh login --
lihat backend/auth/auth.py & README bagian "Autentikasi & Otorisasi" untuk
kenapa ini ditambahkan (data sensitif + API ini akan publik di step 8) dan
bagaimana scope per-wilayah untuk role "pmo" diterapkan di lapisan SQL.

Usage:
    cd backend
    pip install -r requirements.txt   # perlu fastapi, uvicorn, bcrypt, pyjwt
    export JWT_SECRET=<random-panjang>          # WAJIB, lihat auth/auth.py
    python auth/create_user.py --username admin --role admin   # bikin akun pertama
    uvicorn api.main:app --reload --port 8000

Dokumentasi interaktif otomatis: http://localhost:8000/docs
"""
import os
import json
import sqlite3
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Dipakai ulang dari step 3-4 (bukan didefinisikan ulang di sini) supaya
# ambang Sehat/Waspada/Kritis untuk agregat peta (lihat /peta/*) DAN
# penjelasan kriteria di dashboard (/metodologi) selalu konsisten dengan
# kategorisasi & bobot yang benar-benar dipakai menghitung skor -- satu
# sumber kebenaran, bukan angka yang diketik ulang di frontend dan bisa
# diam-diam menyimpang kalau BOBOT/ambang diubah di compute_scores.py.
from scoring.compute_scores import BATAS_SEHAT, BATAS_WASPADA, BOBOT, TURUN_SIGNIFIKAN
from prediction.predict_risk import GAP_BULAN
from auth.auth import (
    JWT_SECRET, CurrentUser, authenticate, create_access_token, get_current_user,
    get_active_user, get_superadmin_user, get_user, init_auth_db, scope_clause,
    list_users, create_user_record, update_user_scope, delete_user_record,
    admin_reset_password, self_change_password, resolve_scope,
)
from auth.settings_store import init_settings_db, load_settings_into_environ, set_setting
# Dipakai ulang dari step 5 (bukan disalin) supaya endpoint /insight/{id} bisa
# generate ON-DEMAND dengan prompt & logika penyimpanan yang PERSIS sama
# dengan mode batch CLI -- lihat catatan "MODE BATCH ... BUKAN satu-satunya
# cara" di docstring generate_insight.py.
from ai_insight.generate_insight import build_client as build_ai_client
from ai_insight.generate_insight import generate_one as generate_insight_one
from ai_insight.generate_insight import load_context as load_insight_context
from ai_insight.generate_insight import simpan as simpan_insight
from ai_insight.generate_insight import CLAUDE_MODEL_DEFAULT, GEMINI_MODEL_DEFAULT

if not JWT_SECRET:
    # Gagal SEKARANG (saat startup), bukan diam-diam sampai request pertama
    # kena error di dalam handler -- kegagalan konfigurasi keamanan harus
    # berisik & langsung ketahuan, bukan menunggu ditemukan user pertama.
    raise RuntimeError(
        "JWT_SECRET belum di-set di environment. Jangan jalankan API tanpa ini "
        "(lihat README bagian Autentikasi) -- export JWT_SECRET=<random-panjang>."
    )

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "..", "data", "output", "sigap_kopdes.db")

LIST_FIELDS_INSIGHT = ["produk_prioritas", "rekomendasi_program"]


def parse_insight_row(row):
    """produk_prioritas & rekomendasi_program disimpan step 5 sebagai JSON
    array di kolom TEXT (SQLite tidak punya tipe list) -- diurai balik jadi
    array asli di sini supaya frontend tidak perlu tahu detail penyimpanan."""
    d = dict(row)
    for field in LIST_FIELDS_INSIGHT:
        if d.get(field):
            try:
                d[field] = json.loads(d[field])
            except (json.JSONDecodeError, TypeError):
                d[field] = [d[field]]
    return d


def kategorikan_agregat(rata_rata):
    if rata_rata is None:
        return None
    if rata_rata >= BATAS_SEHAT:
        return "Sehat"
    if rata_rata >= BATAS_WASPADA:
        return "Waspada"
    return "Kritis"

app = FastAPI(
    title="SIGAP Kopdes API",
    description="Skor kesehatan, prediksi risiko, dan AI insight koperasi KDMP.",
    version="0.1.0",
)
init_auth_db()
init_settings_db()
load_settings_into_environ()

# CORS_ORIGINS dari environment (daftar dipisah koma), default localhost:5173
# untuk dev -- SENGAJA tidak wildcard "*" (beda dari draf awal step 6):
# API ini sekarang butuh Authorization header berisi kredensial sesi, dan
# wildcard CORS + endpoint terautentikasi adalah kombinasi yang lebih mudah
# disalahgunakan lintas-origin. Set CORS_ORIGINS ke domain frontend asli
# begitu deployment (step 8) sudah punya URL final.
_cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LoginBody(BaseModel):
    username: str
    password: str


@app.post("/auth/login")
def login(body: LoginBody):
    """Login dengan username+password, kembalikan JWT (berlaku 8 jam).
    Sertakan token ini sebagai header `Authorization: Bearer <token>` di
    semua request endpoint lain. Akun dibuat lewat `auth/create_user.py`
    atau dashboard Manajemen Akun (admin) -- tidak ada registrasi mandiri
    (lihat README). `must_change_password` true berarti frontend harus
    mengarahkan user ke halaman ganti password SEBELUM apa pun lain --
    endpoint data lain akan menolak (403) selama itu belum dilakukan."""
    user = authenticate(body.username, body.password)
    token = create_access_token(user)
    scope = [s for s in user["kode_wilayah_scope"].split(",") if s]
    return {
        "access_token": token, "token_type": "bearer", "role": user["role"], "scope": scope,
        "must_change_password": bool(user["must_change_password"]),
    }


class ChangePasswordBody(BaseModel):
    password_lama: str
    password_baru: str


@app.post("/auth/change-password")
def change_password(body: ChangePasswordBody, user: CurrentUser = Depends(get_current_user)):
    """Ganti password akun sendiri -- butuh password lama yang benar. Sengaja
    pakai get_current_user (bukan get_active_user) supaya tetap bisa dipanggil
    SAAT must_change_password masih true (justru itu jalan keluarnya)."""
    row = get_user(user.username)
    if row is None:
        raise HTTPException(status_code=401, detail="Akun tidak ditemukan, silakan login ulang.")
    self_change_password(row, body.password_lama, body.password_baru)
    return {"ok": True}


class CreateUserBody(BaseModel):
    username: str
    password: str
    role: str
    kabupaten_list: List[str] = []


class UpdateUserBody(BaseModel):
    role: str
    kabupaten_list: List[str] = []


class ResetPasswordBody(BaseModel):
    password_baru: str


def _validate_role_scope(role: str, kabupaten_list: list) -> list:
    # role 'superadmin' SENGAJA tidak diterima di sini -- sistem ini cuma
    # boleh punya SATU superadmin, selamanya. Kalau boleh dibuat/diubah
    # lewat endpoint ini, superadmin yang sedang login bisa membuat
    # superadmin lain (privilege escalation lewat akun yang sudah mereka
    # kontrol -- bukan cuma soal "kehabisan", tapi soal jumlahnya BISA
    # bertambah tanpa batas). Satu-satunya superadmin dibuat SEKALI lewat
    # CLI saat bootstrap (backend/auth/create_user.py --role superadmin),
    # yang butuh akses shell/server -- batas kepercayaan yang jauh lebih
    # tinggi daripada "sedang login sebagai superadmin lewat browser".
    if role not in ("admin", "pmo"):
        raise HTTPException(
            status_code=422,
            detail="role harus 'admin' atau 'pmo' -- superadmin tidak bisa dibuat/diubah lewat sini "
                   "(cuma boleh ada satu, dibuat sekali lewat CLI saat bootstrap).",
        )
    if role == "pmo" and not kabupaten_list:
        # Sama seperti create_user.py CLI: pmo tanpa scope tidak akan bisa
        # lihat data apa pun (fail closed) -- lebih baik ditolak di sini
        # daripada admin lupa dan membuat akun yang diam-diam tidak berguna.
        raise HTTPException(status_code=422, detail="Role pmo butuh minimal satu kabupaten/kota.")
    if role == "admin":
        return []
    try:
        return resolve_scope(kabupaten_list)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def _kabupaten_for_scope(conn, kode_list: list) -> list:
    if not kode_list:
        return []
    placeholders = ",".join(["?"] * len(kode_list))
    rows = conn.execute(
        f"SELECT DISTINCT kabupaten_kota FROM wilayah WHERE kode_wilayah IN ({placeholders})", kode_list
    ).fetchall()
    return sorted(r["kabupaten_kota"] for r in rows)


class AiKeyBody(BaseModel):
    api_key: str


class AiProviderBody(BaseModel):
    provider: str


class AiModelBody(BaseModel):
    model: str


def _ai_key_env_name() -> str:
    provider = os.environ.get("AI_PROVIDER", "anthropic").lower()
    return "GEMINI_API_KEY" if provider == "gemini" else "ANTHROPIC_API_KEY"


def _ai_model_env_name() -> str:
    provider = os.environ.get("AI_PROVIDER", "anthropic").lower()
    return "GEMINI_MODEL" if provider == "gemini" else "CLAUDE_MODEL"


def _ai_model_default() -> str:
    provider = os.environ.get("AI_PROVIDER", "anthropic").lower()
    return GEMINI_MODEL_DEFAULT if provider == "gemini" else CLAUDE_MODEL_DEFAULT


def _mask_key(value: str) -> str:
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


def _reset_ai_client_cache():
    # _ai_client_cache didefinisikan di bawah (dipakai get_ai_client() untuk
    # endpoint /insight/{id}) -- direferensikan di sini dengan nama yang
    # sama karena semua ini satu modul, sudah selesai dimuat sebelum ada
    # request masuk (lihat get_conn() yang juga dirujuk dari endpoint di
    # atas definisinya). Client LLM di-cache SEKALI per proses (konstruksi
    # client, bukan API key/providernya, yang mahal untuk diulang) -- kalau
    # tidak di-reset di sini, ganti key/provider lewat endpoint di bawah
    # TIDAK akan berlaku (endpoint /insight/{id} tetap pakai client lama
    # yang sudah di-cache dengan key/provider LAMA).
    _ai_client_cache.pop("client", None)


@app.get("/admin/ai-key")
def admin_get_ai_key(superadmin: CurrentUser = Depends(get_superadmin_user)):
    """Status API key provider AI Insight yang AKTIF sekarang. Key aslinya
    TIDAK PERNAH dikirim balik utuh ke frontend, cuma status ada/tidak +
    potongan depan-belakang (buat verifikasi visual "sudah ganti key yang
    benar?"), supaya key yang sudah tersimpan tidak bisa dicuri lewat
    endpoint ini sendiri."""
    env_name = _ai_key_env_name()
    current = os.environ.get(env_name)
    model_env_name = _ai_model_env_name()
    return {
        "provider": os.environ.get("AI_PROVIDER", "anthropic").lower(),
        "env_name": env_name,
        "is_set": bool(current),
        "masked": _mask_key(current) if current else None,
        "model": os.environ.get(model_env_name, _ai_model_default()),
        "model_env_name": model_env_name,
        "model_default": _ai_model_default(),
    }


@app.put("/admin/ai-key")
def admin_set_ai_key(body: AiKeyBody, superadmin: CurrentUser = Depends(get_superadmin_user)):
    """Ganti API key provider AI Insight yang AKTIF SEKARANG (lihat
    /admin/ai-provider untuk ganti provider-nya). Disimpan ke auth.db
    (survive restart -- lihat settings_store.py) DAN langsung menimpa
    os.environ proses ini (berlaku SEKETIKA tanpa restart, karena
    build_client() di ai_insight/generate_insight.py baca os.environ FRESH
    tiap dipanggil, bukan di-cache saat import)."""
    api_key = body.api_key.strip()
    if not api_key:
        raise HTTPException(status_code=422, detail="API key tidak boleh kosong.")
    env_name = _ai_key_env_name()
    set_setting(env_name, api_key)
    os.environ[env_name] = api_key
    _reset_ai_client_cache()
    return {"ok": True}


@app.put("/admin/ai-provider")
def admin_set_ai_provider(body: AiProviderBody, superadmin: CurrentUser = Depends(get_superadmin_user)):
    """Ganti provider LLM aktif (anthropic/gemini) untuk AI Insight. Sama
    seperti /admin/ai-key: disimpan ke auth.db DAN langsung menimpa
    os.environ proses ini, berlaku seketika tanpa restart -- lihat
    _current_provider() di ai_insight/generate_insight.py yang baca
    AI_PROVIDER fresh tiap dipanggil (BUKAN konstanta modul yang di-cache
    saat import, seperti sebelumnya -- itu sebabnya dulu ganti provider
    butuh restart proses, sekarang tidak)."""
    provider = body.provider.strip().lower()
    if provider not in ("anthropic", "gemini"):
        raise HTTPException(status_code=422, detail="provider harus 'anthropic' atau 'gemini'.")
    set_setting("AI_PROVIDER", provider)
    os.environ["AI_PROVIDER"] = provider
    _reset_ai_client_cache()
    return {"ok": True}


@app.put("/admin/ai-model")
def admin_set_ai_model(body: AiModelBody, superadmin: CurrentUser = Depends(get_superadmin_user)):
    """Ganti id model (atau daftar id model dipisah koma -- fallback chain,
    lihat _model_candidates() di ai_insight/generate_insight.py) untuk
    provider AI Insight yang AKTIF SEKARANG. Kalau lebih dari satu, dicoba
    BERURUTAN: model pertama gagal (kuota habis, model tidak ada, dst)
    otomatis lanjut ke model berikutnya sebelum benar-benar menyerah. Tiap
    id TIDAK divalidasi di sini (katalog model provider berubah dari waktu
    ke waktu, termasuk rilis yang belum diketahui saat kode ini ditulis) --
    kalau salah/tidak ada, provider sendiri yang menolak lewat error API
    biasa. Sama seperti /admin/ai-key & /admin/ai-provider: disimpan ke
    auth.db DAN langsung menimpa os.environ, berlaku seketika tanpa
    restart."""
    model = body.model.strip()
    if not model:
        raise HTTPException(status_code=422, detail="Id model tidak boleh kosong.")
    env_name = _ai_model_env_name()
    set_setting(env_name, model)
    os.environ[env_name] = model
    return {"ok": True}


@app.get("/admin/kabupaten")
def admin_list_kabupaten(superadmin: CurrentUser = Depends(get_superadmin_user)):
    """Daftar nama kabupaten/kota SAJA (bukan wilayah/koperasi) -- dipakai
    form Tambah/Edit Akun buat pilih scope PMO. Endpoint TERPISAH dari
    /wilayah (yang butuh get_active_user + scope_clause dan karena itu
    balik KOSONG untuk superadmin, fail closed) -- superadmin memang tidak
    boleh lihat data koperasi/wilayah sama sekali, tapi tetap perlu tahu
    NAMA kabupaten/kota yang ada supaya bisa pilih scope PMO tanpa mengetik
    manual (rawan salah ketik -- lihat resolve_kabupaten di auth/auth.py
    yang match persis by name)."""
    conn = get_conn()
    try:
        rows = conn.execute("SELECT DISTINCT kabupaten_kota FROM wilayah ORDER BY kabupaten_kota").fetchall()
        return [r["kabupaten_kota"] for r in rows]
    finally:
        conn.close()


@app.get("/admin/users")
def admin_list_users(superadmin: CurrentUser = Depends(get_superadmin_user)):
    """Daftar semua akun -- untuk dashboard Manajemen Akun. kode_wilayah_scope
    mentah TIDAK dikirim ke frontend (bisa ribuan kode) -- diringkas jadi
    daftar nama kabupaten/kota (kabupaten_list) yang lebih enak dibaca &
    diedit ulang."""
    users = list_users()
    conn = get_conn()
    try:
        for u in users:
            scope = [s for s in u["kode_wilayah_scope"].split(",") if s]
            u["jumlah_wilayah"] = len(scope)
            u["kabupaten_list"] = _kabupaten_for_scope(conn, scope) if u["role"] == "pmo" else []
            u["must_change_password"] = bool(u["must_change_password"])
            del u["kode_wilayah_scope"]
    finally:
        conn.close()
    return users


@app.post("/admin/users")
def admin_create_user(body: CreateUserBody, superadmin: CurrentUser = Depends(get_superadmin_user)):
    """Buat akun baru. Password dipilih superadmin di sini, jadi akun baru
    SELALU dibuat dengan must_change_password=true (lihat
    create_user_record) -- pemiliknya wajib menggantinya di login pertama."""
    username = body.username.strip()
    if not username:
        raise HTTPException(status_code=422, detail="Username wajib diisi.")
    scope = _validate_role_scope(body.role, body.kabupaten_list)
    try:
        create_user_record(username, body.password, body.role, scope, must_change_password=True)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"ok": True}


@app.put("/admin/users/{username}")
def admin_update_user(username: str, body: UpdateUserBody, superadmin: CurrentUser = Depends(get_superadmin_user)):
    """Ubah role & scope wilayah akun (BUKAN password -- lihat
    /admin/users/{username}/reset-password untuk itu)."""
    target = get_user(username)
    if target is None:
        raise HTTPException(status_code=404, detail="Akun tidak ditemukan.")
    if target["role"] == "superadmin":
        # Termasuk akun superadmin yang sedang login sendiri -- tidak ada
        # role tujuan yang valid buat akun ini lewat endpoint ini (role
        # 'superadmin' ditolak _validate_role_scope, dan menurunkannya ke
        # admin/pmo lewat sini berarti sistem BISA berakhir tanpa
        # superadmin sama sekali). Satu-satunya superadmin memang sengaja
        # tidak bisa diubah lewat portal ini -- lihat auth/create_user.py.
        raise HTTPException(
            status_code=400,
            detail="Akun superadmin tidak bisa diubah lewat sini -- gunakan CLI (backend/auth/create_user.py) kalau memang perlu.",
        )
    scope = _validate_role_scope(body.role, body.kabupaten_list)
    update_user_scope(username, body.role, scope)
    return {"ok": True}


@app.post("/admin/users/{username}/reset-password")
def admin_reset_user_password(username: str, body: ResetPasswordBody, superadmin: CurrentUser = Depends(get_superadmin_user)):
    """Set password baru untuk akun lain (mis. lupa password) -- SELALU
    menyalakan lagi must_change_password (lihat admin_reset_password),
    karena superadmin di sini yang tahu password barunya, bukan pemilik
    akun."""
    if get_user(username) is None:
        raise HTTPException(status_code=404, detail="Akun tidak ditemukan.")
    try:
        admin_reset_password(username, body.password_baru)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"ok": True}


@app.delete("/admin/users/{username}")
def admin_delete_user(username: str, superadmin: CurrentUser = Depends(get_superadmin_user)):
    """Hapus akun. Akun superadmin (termasuk akun sendiri -- sistem ini
    cuma boleh punya satu, jadi username yang bukan superadmin.username
    pun tidak akan pernah punya role superadmin) tidak bisa dihapus lewat
    sini -- gunakan akses langsung ke database kalau memang perlu."""
    target = get_user(username)
    if target is None:
        raise HTTPException(status_code=404, detail="Akun tidak ditemukan.")
    if target["role"] == "superadmin":
        raise HTTPException(
            status_code=400,
            detail="Akun superadmin tidak bisa dihapus lewat sini -- gunakan akses langsung ke database kalau memang perlu.",
        )
    delete_user_record(username)
    return {"ok": True}


def get_conn():
    if not os.path.exists(DB_PATH):
        raise HTTPException(
            status_code=503,
            detail="sigap_kopdes.db belum ada -- jalankan pipeline step 2-4 dulu "
                   "(lihat README bagian 'Menjalankan step 2/3/4').",
        )
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def table_exists(conn, name):
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def periode_terbaru(conn):
    row = conn.execute("SELECT MAX(periode) AS p FROM skor_kesehatan").fetchone()
    if row is None or row["p"] is None:
        raise HTTPException(status_code=503, detail="Tabel skor_kesehatan kosong -- jalankan step 3 dulu.")
    return row["p"]


@app.get("/")
def root():
    return {"nama": "SIGAP Kopdes API", "docs": "/docs"}


@app.get("/metodologi")
def metodologi(user: CurrentUser = Depends(get_active_user)):
    """Angka & ambang di balik kategori Sehat/Waspada/Kritis dan komponen
    skor -- dipakai halaman "Kriteria & Metodologi" di dashboard supaya
    penjelasannya tidak pernah menyimpang dari rumus yang benar-benar
    dipakai compute_scores.py & predict_risk.py (satu sumber kebenaran,
    bukan angka yang diketik ulang manual di frontend)."""
    return {
        "bobot_skor_komposit": BOBOT,
        "batas_sehat": BATAS_SEHAT,
        "batas_waspada": BATAS_WASPADA,
        "turun_signifikan": TURUN_SIGNIFIKAN,
        "gap_bulan_prediksi": GAP_BULAN,
    }


@app.get("/wilayah")
def list_wilayah(user: CurrentUser = Depends(get_active_user)):
    """Daftar wilayah + profil IDM gabungan -- untuk filter/peta di dashboard.
    Role pmo hanya melihat wilayah dalam scope-nya."""
    conn = get_conn()
    try:
        clause, params = scope_clause(user, "w")
        rows = conn.execute(f"""
            SELECT w.*, p.status_idm, p.skor_idm, p.mata_pencaharian_dominan,
                   p.akses_pusat_perdagangan
            FROM wilayah w
            LEFT JOIN profil_wilayah p ON p.kode_wilayah = w.kode_wilayah
            WHERE 1=1 {clause}
            ORDER BY w.provinsi, w.kabupaten_kota, w.desa_kelurahan
        """, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@app.get("/koperasi")
def list_koperasi(kategori: Optional[str] = None, kode_wilayah: Optional[str] = None,
                   kabupaten_kota: Optional[str] = None, provinsi: Optional[str] = None,
                   periode: Optional[str] = None, user: CurrentUser = Depends(get_active_user)):
    """Daftar koperasi + skor, prediksi, dan koordinat pada satu periode (default: terbaru).

    Query params opsional: kategori (Sehat/Waspada/Kritis), kode_wilayah,
    kabupaten_kota, provinsi, periode (YYYY-MM). latitude/longitude disertakan
    untuk kebutuhan marker individual di halaman Peta (level koperasi).
    Role pmo hanya melihat koperasi dalam scope wilayahnya.
    """
    conn = get_conn()
    try:
        p = periode or periode_terbaru(conn)
        clause, scope_params = scope_clause(user, "w")
        sql = f"""
            SELECT k.koperasi_id, k.nama_koperasi, k.jenis_usaha, k.status_operasional,
                   k.jumlah_anggota, k.kode_wilayah,
                   w.provinsi, w.kabupaten_kota, w.desa_kelurahan, w.latitude, w.longitude,
                   s.periode, s.skor_komposit, s.kategori, s.prediksi_risiko_3bln
            FROM koperasi k
            JOIN wilayah w ON w.kode_wilayah = k.kode_wilayah
            LEFT JOIN skor_kesehatan s ON s.koperasi_id = k.koperasi_id AND s.periode = ?
            WHERE 1=1 {clause}
        """
        params = [p, *scope_params]
        if kategori:
            sql += " AND s.kategori = ?"
            params.append(kategori)
        if kode_wilayah:
            sql += " AND k.kode_wilayah = ?"
            params.append(kode_wilayah)
        if kabupaten_kota:
            sql += " AND w.kabupaten_kota = ?"
            params.append(kabupaten_kota)
        if provinsi:
            sql += " AND w.provinsi = ?"
            params.append(provinsi)
        sql += " ORDER BY k.koperasi_id"
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@app.get("/koperasi/{koperasi_id}")
def detail_koperasi(koperasi_id: str, user: CurrentUser = Depends(get_active_user)):
    """Detail satu koperasi: profil, histori skor semua periode, dan AI insight terbaru (jika ada).
    404 juga dikembalikan kalau koperasi ada tapi DI LUAR scope wilayah pmo --
    disatukan dengan "tidak ditemukan" (bukan 403) supaya tidak membocorkan
    ke pmo bahwa koperasi_id tsb sebenarnya ada di wilayah lain."""
    conn = get_conn()
    try:
        clause, scope_params = scope_clause(user, "w")
        koperasi = conn.execute(f"""
            SELECT k.*, w.provinsi, w.kabupaten_kota, w.kecamatan, w.desa_kelurahan,
                   w.pmo_penanggung_jawab,
                   p.status_idm, p.skor_idm, p.mata_pencaharian_dominan,
                   p.akses_pusat_perdagangan
            FROM koperasi k
            JOIN wilayah w ON w.kode_wilayah = k.kode_wilayah
            LEFT JOIN profil_wilayah p ON p.kode_wilayah = k.kode_wilayah
            WHERE k.koperasi_id = ? {clause}
        """, [koperasi_id, *scope_params]).fetchone()
        if koperasi is None:
            raise HTTPException(status_code=404, detail=f"Koperasi {koperasi_id} tidak ditemukan.")

        histori_skor = conn.execute("""
            SELECT periode, skor_transaksi, skor_stok, skor_pelaporan, skor_komposit,
                   kategori, prediksi_risiko_3bln
            FROM skor_kesehatan
            WHERE koperasi_id = ?
            ORDER BY periode
        """, (koperasi_id,)).fetchall()

        insight = None
        if table_exists(conn, "ai_insight"):
            insight_row = conn.execute("""
                SELECT * FROM ai_insight
                WHERE koperasi_id = ?
                ORDER BY periode DESC
                LIMIT 1
            """, (koperasi_id,)).fetchone()
            if insight_row is not None:
                insight = parse_insight_row(insight_row)

        return {
            "koperasi": dict(koperasi),
            "histori_skor": [dict(r) for r in histori_skor],
            "ai_insight_terbaru": insight,
        }
    finally:
        conn.close()


@app.get("/skor")
def list_skor(periode: Optional[str] = None, koperasi_id: Optional[str] = None,
              user: CurrentUser = Depends(get_active_user)):
    """Baris skor_kesehatan mentah, difilter opsional per periode dan/atau koperasi.
    Di-JOIN ke koperasi hanya untuk menerapkan scope wilayah pmo (kolom yang
    dikembalikan tetap murni skor_kesehatan.*)."""
    conn = get_conn()
    try:
        clause, scope_params = scope_clause(user, "k")
        sql = f"""
            SELECT s.* FROM skor_kesehatan s
            JOIN koperasi k ON k.koperasi_id = s.koperasi_id
            WHERE 1=1 {clause}
        """
        params = list(scope_params)
        if periode:
            sql += " AND s.periode = ?"
            params.append(periode)
        if koperasi_id:
            sql += " AND s.koperasi_id = ?"
            params.append(koperasi_id)
        sql += " ORDER BY s.koperasi_id, s.periode"
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@app.get("/notifikasi")
def list_notifikasi(status_tindak_lanjut: Optional[str] = None, koperasi_id: Optional[str] = None,
                     user: CurrentUser = Depends(get_active_user)):
    """Daftar notifikasi otomatis dari step 3 (penurunan skor signifikan, dsb).
    Di-JOIN ke koperasi hanya untuk scope wilayah pmo."""
    conn = get_conn()
    try:
        clause, scope_params = scope_clause(user, "k")
        sql = f"""
            SELECT n.* FROM notifikasi n
            JOIN koperasi k ON k.koperasi_id = n.koperasi_id
            WHERE 1=1 {clause}
        """
        params = list(scope_params)
        if status_tindak_lanjut:
            sql += " AND n.status_tindak_lanjut = ?"
            params.append(status_tindak_lanjut)
        if koperasi_id:
            sql += " AND n.koperasi_id = ?"
            params.append(koperasi_id)
        sql += " ORDER BY n.tanggal DESC"
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def ringkas_error_llm(e):
    """Error mentah dari SDK provider LLM (Anthropic/Gemini) berupa blob JSON
    panjang yang tidak enak ditampilkan ke pengguna dashboard. Dikenali
    beberapa pola umum (kuota habis, rate limit) jadi pesan Indonesia yang
    jelas & actionable; selain itu fallback ke potongan pesan asli (bukan
    seluruh traceback/dict provider) -- ditemukan penting saat kuota gratis
    Gemini (20 request/hari untuk gemini-3.7-flash) sungguhan habis saat
    pengujian dan pesannya awalnya jadi dump JSON mentah + prefix dobel
    (backend & frontend sama-sama menambahkan "Gagal membuat AI insight:")."""
    teks = str(e)
    rendah = teks.lower()
    if "429" in teks or "quota" in rendah or "rate" in rendah or "too_many_requests" in rendah:
        return (
            "Kuota API provider LLM untuk hari ini sudah habis (tier gratis biasanya dibatasi "
            "puluhan request/hari). Coba lagi nanti, atau ganti AI_PROVIDER di server -- lihat "
            "README bagian 'Menjalankan step 5'."
        )
    return f"Panggilan LLM gagal: {teks[:200]}"


_ai_client_cache = {}


def get_ai_client():
    """Client provider LLM aktif, dibuat sekali per proses lalu dipakai ulang
    (bukan sekali per request -- konstruksinya murah tapi tidak perlu diulang).
    Melempar RuntimeError kalau API key belum di-set, ditangkap pemanggil jadi
    HTTPException 503 (bukan 500) -- ini kegagalan KONFIGURASI, bukan bug."""
    if "client" not in _ai_client_cache:
        _ai_client_cache["client"] = build_ai_client()
    return _ai_client_cache["client"]


@app.get("/insight/{koperasi_id}")
def get_insight(koperasi_id: str, periode: Optional[str] = None, user: CurrentUser = Depends(get_active_user)):
    """AI insight (narasi + rekomendasi) untuk satu koperasi.

    Kalau sudah pernah dibuat (step 5 batch ATAU dipanggil sebelumnya lewat
    endpoint ini), dikembalikan langsung dari cache di tabel ai_insight --
    TANPA memanggil LLM lagi. Kalau BELUM ada, di-generate ON-DEMAND di sini
    juga (realtime, ~2-5 detik) lalu disimpan supaya request berikutnya untuk
    koperasi yang sama tidak perlu panggil LLM ulang. Ini prinsip utamanya:
    kuota API cuma terpakai untuk koperasi yang SUNGGUH dibuka penggunanya,
    bukan di-batch untuk seluruh koperasi di muka (lihat generate_insight.py).

    404 kalau koperasi tidak ada / di luar scope pmo. 503 kalau server belum
    dikonfigurasi API key provider (ANTHROPIC_API_KEY/GEMINI_API_KEY). 502
    kalau panggilan LLM-nya sendiri gagal (rate limit, jaringan, dst)."""
    conn = get_conn()
    try:
        clause, scope_params = scope_clause(user, "k")
        in_scope = conn.execute(f"SELECT 1 FROM koperasi k WHERE k.koperasi_id = ? {clause}",
                                 [koperasi_id, *scope_params]).fetchone()
        if in_scope is None:
            raise HTTPException(status_code=404, detail=f"Koperasi {koperasi_id} tidak ditemukan.")

        if table_exists(conn, "ai_insight"):
            sql = "SELECT * FROM ai_insight WHERE koperasi_id = ?"
            params = [koperasi_id]
            if periode:
                sql += " AND periode = ?"
                params.append(periode)
            sql += " ORDER BY periode DESC LIMIT 1"
            row = conn.execute(sql, params).fetchone()
            if row is not None:
                return parse_insight_row(row)
    finally:
        conn.close()

    # Belum ada di cache -- generate sekarang.
    try:
        client = get_ai_client()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    df = load_insight_context(koperasi_id=koperasi_id, periode=periode)
    if df.empty:
        raise HTTPException(status_code=404, detail=f"Koperasi {koperasi_id} tidak ditemukan atau belum ada skor untuk periode ini.")

    try:
        out = generate_insight_one(df.iloc[0], client)
    except Exception as e:
        raise HTTPException(status_code=502, detail=ringkas_error_llm(e))

    simpan_insight([out])
    return parse_insight_row(out)


@app.get("/ringkasan")
def ringkasan(periode: Optional[str] = None, user: CurrentUser = Depends(get_active_user)):
    """Ringkasan agregat untuk kartu-kartu dashboard: jumlah koperasi per kategori,
    rata-rata skor komposit, dan jumlah notifikasi yang belum ditindaklanjuti.
    Semua di-scope ke wilayah pmo lewat JOIN ke koperasi."""
    conn = get_conn()
    try:
        p = periode or periode_terbaru(conn)
        clause, scope_params = scope_clause(user, "k")
        per_kategori = conn.execute(f"""
            SELECT s.kategori AS kategori, COUNT(*) AS jumlah
            FROM skor_kesehatan s
            JOIN koperasi k ON k.koperasi_id = s.koperasi_id
            WHERE s.periode = ? {clause}
            GROUP BY s.kategori
        """, [p, *scope_params]).fetchall()
        rata_rata = conn.execute(f"""
            SELECT AVG(s.skor_komposit) AS rata_rata
            FROM skor_kesehatan s
            JOIN koperasi k ON k.koperasi_id = s.koperasi_id
            WHERE s.periode = ? {clause}
        """, [p, *scope_params]).fetchone()
        # "Baru" adalah status awal yang ditulis compute_scores.py (step 3) untuk
        # SETIAP notifikasi yang diterbitkan -- belum ada alur di sistem ini yang
        # mengubah status_tindak_lanjut ke nilai lain, jadi "Baru" == belum ditindaklanjuti.
        notif_belum = conn.execute(f"""
            SELECT COUNT(*) AS jumlah
            FROM notifikasi n
            JOIN koperasi k ON k.koperasi_id = n.koperasi_id
            WHERE n.status_tindak_lanjut = 'Baru' {clause}
        """, scope_params).fetchone()

        return {
            "periode": p,
            "per_kategori": {r["kategori"]: r["jumlah"] for r in per_kategori},
            "rata_rata_skor_komposit": round(rata_rata["rata_rata"], 1) if rata_rata["rata_rata"] is not None else None,
            "notifikasi_belum_ditindaklanjuti": notif_belum["jumlah"],
        }
    finally:
        conn.close()


def _agregat_wilayah_rows(conn, group_by_col, periode, where_extra="", where_params=()):
    """Query bersama untuk /peta/provinsi & /peta/kabupaten -- beda cuma kolom
    GROUP BY dan filter tambahan. Kategori agregat dihitung dari skor
    RATA-RATA wilayah dengan ambang yang sama seperti skor individual
    (BATAS_SEHAT/BATAS_WASPADA) -- ini kesederhanaan yang disengaja, bukan
    berarti semua koperasi di wilayah itu senyatanya berkategori sama."""
    sql = f"""
        SELECT w.{group_by_col} AS nama,
               AVG(w.latitude) AS lat, AVG(w.longitude) AS lon,
               COUNT(DISTINCT k.koperasi_id) AS jumlah_koperasi,
               AVG(s.skor_komposit) AS rata_rata_skor,
               SUM(CASE WHEN s.kategori = 'Sehat' THEN 1 ELSE 0 END) AS sehat,
               SUM(CASE WHEN s.kategori = 'Waspada' THEN 1 ELSE 0 END) AS waspada,
               SUM(CASE WHEN s.kategori = 'Kritis' THEN 1 ELSE 0 END) AS kritis
        FROM koperasi k
        JOIN wilayah w ON w.kode_wilayah = k.kode_wilayah
        LEFT JOIN skor_kesehatan s ON s.koperasi_id = k.koperasi_id AND s.periode = ?
        WHERE 1=1 {where_extra}
        GROUP BY w.{group_by_col}
        ORDER BY w.{group_by_col}
    """
    rows = conn.execute(sql, [periode, *where_params]).fetchall()
    hasil = []
    for r in rows:
        rata = round(r["rata_rata_skor"], 1) if r["rata_rata_skor"] is not None else None
        hasil.append({
            "nama": r["nama"],
            "latitude": round(r["lat"], 5) if r["lat"] is not None else None,
            "longitude": round(r["lon"], 5) if r["lon"] is not None else None,
            "jumlah_koperasi": r["jumlah_koperasi"],
            "rata_rata_skor": rata,
            "kategori_agregat": kategorikan_agregat(rata),
            "per_kategori": {"Sehat": r["sehat"], "Waspada": r["waspada"], "Kritis": r["kritis"]},
        })
    return hasil


@app.get("/peta/provinsi")
def peta_provinsi(periode: Optional[str] = None, user: CurrentUser = Depends(get_active_user)):
    """Agregat kesehatan koperasi per provinsi -- level 1 drill-down peta.
    Titik lat/lon adalah rata-rata koordinat wilayah di provinsi itu (perkiraan
    visual, bukan centroid administratif resmi -- lihat generate_data.py).
    pmo hanya melihat provinsi yang punya wilayah dalam scope-nya, dan
    hitungannya cuma mencakup koperasi dalam scope itu."""
    conn = get_conn()
    try:
        p = periode or periode_terbaru(conn)
        clause, scope_params = scope_clause(user, "w")
        return {"periode": p, "provinsi": _agregat_wilayah_rows(conn, "provinsi", p, clause, scope_params)}
    finally:
        conn.close()


@app.get("/peta/kabupaten")
def peta_kabupaten(provinsi: str, periode: Optional[str] = None, user: CurrentUser = Depends(get_active_user)):
    """Agregat kesehatan koperasi per kabupaten/kota DALAM SATU provinsi --
    level 2 drill-down peta (diklik dari satu titik provinsi di /peta/provinsi)."""
    conn = get_conn()
    try:
        p = periode or periode_terbaru(conn)
        clause, scope_params = scope_clause(user, "w")
        hasil = _agregat_wilayah_rows(conn, "kabupaten_kota", p, f"AND w.provinsi = ?{clause}", [provinsi, *scope_params])
        return {"periode": p, "provinsi": provinsi, "kabupaten": hasil}
    finally:
        conn.close()
