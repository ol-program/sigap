"""
SIGAP Kopdes - Buat/Update Akun Login
========================================
Tidak ada halaman registrasi di dashboard (ini alat internal untuk PMO,
bukan aplikasi publik) -- akun dibuat lewat CLI ini oleh admin sistem.
Password diminta lewat prompt tersembunyi (getpass), tidak pernah lewat
argumen command-line (yang bisa bocor ke shell history / `ps aux`).

Usage:
    # Admin (akses semua wilayah):
    python create_user.py --username admin1 --role admin

    # PMO dibatasi ke satu kabupaten/kota (resolve otomatis semua
    # kode_wilayah di kabupaten itu dari sigap_kopdes.db):
    python create_user.py --username pmo_bandung --role pmo --kabupaten "Kab. Bandung"

    # PMO dengan kode_wilayah spesifik (kalau butuh kontrol lebih presisi):
    python create_user.py --username pmo_custom --role pmo --kode-wilayah W0001,W0002

Menjalankan ulang dengan --username yang sama akan mengganti password &
scope akun itu (UPSERT), bukan menduplikasi.
"""
import os
import sys
import argparse
import getpass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from auth import init_auth_db, get_auth_conn, hash_password, resolve_kabupaten as _resolve_kabupaten  # noqa: E402


def resolve_kabupaten(nama_kabupaten):
    # Tipis di atas auth.resolve_kabupaten() (satu sumber kebenaran, dipakai
    # juga oleh endpoint admin di api/main.py) -- di sini cuma diterjemahkan
    # dari ValueError ke print+exit yang lebih pas untuk CLI.
    try:
        return _resolve_kabupaten(nama_kabupaten)
    except ValueError as e:
        print(str(e))
        sys.exit(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--username", required=True)
    ap.add_argument("--role", required=True, choices=["admin", "pmo", "superadmin"])
    ap.add_argument("--kabupaten", help="Nama kabupaten_kota persis seperti di tabel wilayah, mis. 'Kab. Bandung' -- untuk role=pmo")
    ap.add_argument("--kode-wilayah", help="Daftar kode_wilayah dipisah koma, mis. W0001,W0002 -- alternatif dari --kabupaten")
    args = ap.parse_args()

    if args.role == "pmo" and not args.kabupaten and not args.kode_wilayah:
        print("role=pmo butuh --kabupaten atau --kode-wilayah (PMO tanpa scope tidak akan bisa lihat data apa pun -- fail closed).")
        sys.exit(1)

    if args.role == "superadmin":
        # Sistem ini cuma boleh punya SATU superadmin, selamanya -- endpoint
        # admin (/admin/users lewat portal frontend-admin/) sengaja MENOLAK
        # membuat/mengubah akun jadi superadmin sama sekali (lihat
        # _validate_role_scope di api/main.py), justru supaya jalur SATU-
        # SATUNYA untuk (mengganti) superadmin adalah di sini -- CLI yang
        # butuh akses shell/server, bukan tombol di browser. --username yang
        # SAMA dengan superadmin yang sudah ada tetap boleh (itu cuma reset
        # password/upsert akun itu sendiri, bukan menambah superadmin baru).
        init_auth_db()
        conn = get_auth_conn()
        existing = conn.execute(
            "SELECT username FROM users WHERE role = 'superadmin' AND username != ?", (args.username,)
        ).fetchone()
        conn.close()
        if existing:
            print(
                f"Sudah ada akun superadmin lain ('{existing['username']}') -- sistem ini cuma boleh punya SATU "
                "superadmin. Hapus/ubah role akun itu dulu langsung lewat auth.db kalau memang ingin menggantinya."
            )
            sys.exit(1)

    scope = []
    if args.role == "pmo":
        scope = resolve_kabupaten(args.kabupaten) if args.kabupaten else [w.strip() for w in args.kode_wilayah.split(",")]

    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Ulangi password: ")
    if password != confirm:
        print("Password tidak cocok.")
        sys.exit(1)
    if len(password) < 8:
        print("Password minimal 8 karakter.")
        sys.exit(1)

    init_auth_db()
    conn = get_auth_conn()
    # must_change_password selalu 1 di sini (baik akun baru maupun password
    # yang di-reset lewat --username yang sama) -- password ini diketik
    # admin lewat prompt, jadi pemiliknya WAJIB menggantinya sebelum bisa
    # login sungguhan.
    conn.execute("""
        INSERT INTO users (username, password_hash, role, kode_wilayah_scope, must_change_password)
        VALUES (?, ?, ?, ?, 1)
        ON CONFLICT(username) DO UPDATE SET
            password_hash = excluded.password_hash,
            role = excluded.role,
            kode_wilayah_scope = excluded.kode_wilayah_scope,
            must_change_password = 1
    """, (args.username, hash_password(password), args.role, ",".join(scope)))
    conn.commit()
    conn.close()

    if args.role == "admin":
        lingkup = "SEMUA wilayah (data koperasi)"
    elif args.role == "superadmin":
        lingkup = "manajemen akun (portal frontend-admin/) -- BUKAN data koperasi"
    else:
        lingkup = f"{len(scope)} wilayah ({args.kabupaten or args.kode_wilayah})"
    print(f"OK: akun '{args.username}' ({args.role}) tersimpan, akses ke {lingkup}.")


if __name__ == "__main__":
    main()
