"""
SIGAP Kopdes - Config Tersimpan (provider & API key AI Insight, dkk)

Disimpan di auth.db (bukan sigap_kopdes.db, yang ditulis ulang total tiap
generate_data.py dijalankan) supaya superadmin bisa ganti provider/API key
AI Insight lewat portal Manajemen Akun tanpa akses shell/redeploy -- lihat
endpoint /admin/ai-key & /admin/ai-provider di api/main.py.

Env var tetap jadi nilai awal/fallback. Begitu diganti lewat UI, nilai di
tabel settings jadi sumber kebenaran: menimpa os.environ proses yang sedang
jalan (berlaku seketika, lihat load_settings_into_environ()) dan tetap
dipakai setelah restart -- termasuk mengalahkan env var baru di
.env.production kalau file itu diedit ulang tanpa juga mengganti value-nya
lewat UI.
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
    """Dipanggil sekali saat startup API -- timpa env var proses ini dengan
    key/provider yang pernah diganti lewat UI (tersimpan di auth.db)."""
    for key in (
        "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "OLLAMA_API_KEY",
        "AI_PROVIDER", "CLAUDE_MODEL", "GEMINI_MODEL", "OLLAMA_MODEL",
    ):
        value = get_setting(key)
        if value:
            os.environ[key] = value
