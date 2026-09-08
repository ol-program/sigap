"""
SIGAP Kopdes - Config Tersimpan (provider & API key AI Insight, dkk)
======================================================================
Kenapa file terpisah dari auth.py: fungsinya beda (bukan akun/sesi login),
TAPI disimpan di auth.db yang SAMA (bukan bikin file .db baru) karena
sifatnya sama -- config operasional yang harus SELAMAT dari
generate_data.py menulis ulang sigap_kopdes.db total (lihat auth.py untuk
alasan yang sama soal tabel users).

Provider & API key AI (AI_PROVIDER, ANTHROPIC_API_KEY/GEMINI_API_KEY/
OLLAMA_API_KEY, lihat ai_insight/generate_insight.py) awalnya HANYA bisa diset lewat
environment variable saat proses start. Ditambahkan di sini supaya
superadmin bisa ganti keduanya lewat portal Manajemen Akun
(frontend-admin/) TANPA akses shell/redeploy -- lihat endpoint
/admin/ai-key & /admin/ai-provider di api/main.py & README bagian "Portal
Superadmin".

Env var (`export ANTHROPIC_API_KEY=...` sebelum start) tetap jadi nilai
AWAL/fallback (dipakai kalau belum pernah diganti lewat UI). Begitu diganti
lewat UI, nilai di tabel `settings` ini jadi sumber kebenaran: langsung
menimpa `os.environ` proses yang sedang jalan (berlaku SEKETIKA, tanpa
restart -- build_client() di generate_insight.py baca os.environ FRESH
tiap dipanggil, bukan di-cache saat import) sekaligus dipakai lagi setiap
kali proses restart (lihat load_settings_into_environ(), dipanggil saat
startup API di api/main.py).
"""
import os

from auth.auth import get_auth_conn


def init_settings_db():
    conn = get_auth_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def get_setting(key: str):
    conn = get_auth_conn()
    try:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None
    finally:
        conn.close()


def set_setting(key: str, value: str):
    conn = get_auth_conn()
    try:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        conn.commit()
    finally:
        conn.close()


def load_settings_into_environ():
    """Dipanggil sekali saat startup API (lihat api/main.py) -- kalau ada
    key/provider yang PERNAH diganti lewat UI (tersimpan di auth.db), timpa
    env var proses ini supaya konsisten dengan yang terakhir di-set lewat
    UI, bukan env var lama/usang yang kebetulan masih ter-export di shell."""
    for key in (
        "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "OLLAMA_API_KEY",
        "AI_PROVIDER", "CLAUDE_MODEL", "GEMINI_MODEL", "OLLAMA_MODEL",
    ):
        value = get_setting(key)
        if value:
            os.environ[key] = value
