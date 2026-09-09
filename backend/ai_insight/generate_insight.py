"""
SIGAP Kopdes - AI Insight & Rekomendasi (Step 5)

Memanggil LLM untuk menghasilkan, per koperasi: narasi kondisi, satu
rekomendasi tindakan (dari skor & tren step 3-4), dan tiga jenis saran
pengembangan usaha berbasis profil wilayah/IDM:
  - produk_prioritas   : 2-3 ide produk/jasa sesuai mata pencaharian &
                          keragaman ekonomi wilayah
  - rekomendasi_promosi: satu ide kampanye/promosi beserta momentum waktunya
  - rekomendasi_program: 2-3 ide program non-produk dari dimensi sosial/
                          ekonomi/lingkungan & akses pasar wilayah

Prompt hanya berisi angka yang sudah dihitung step 2-4 (skor, prediksi,
profil wilayah) -- LLM menarasikan & menyarankan, tidak menghitung ulang
atau mengarang angka baru.

Tiga provider LLM didukung lewat env var AI_PROVIDER (default "anthropic"):

  AI_PROVIDER=anthropic (default) -- butuh ANTHROPIC_API_KEY:
      export ANTHROPIC_API_KEY=sk-ant-...
      pip install anthropic

  AI_PROVIDER=gemini -- Google AI Studio, butuh GEMINI_API_KEY:
      export AI_PROVIDER=gemini
      export GEMINI_API_KEY=...          # dari https://aistudio.google.com/apikey
      pip install google-genai

  AI_PROVIDER=ollama -- Ollama Cloud API (https://ollama.com, bukan server
  Ollama lokal), butuh OLLAMA_API_KEY:
      export AI_PROVIDER=ollama
      export OLLAMA_API_KEY=...          # dari https://ollama.com/settings/keys
      pip install ollama

PROMPT_TEMPLATE sama untuk ketiga provider -- yang beda cuma pemanggilan API
(panggil_claude/panggil_gemini/panggil_ollama).

Mode batch (CLI) bukan satu-satunya cara insight dibuat: build_client() dan
generate_one() dipakai ulang oleh backend API (GET /insight/{koperasi_id})
untuk generate on-demand saat halaman detail koperasi dibuka.

Usage:
    python generate_insight.py --dry-run                    # cek prompt, tanpa panggil API
    python generate_insight.py --dry-run --koperasi KDMP-00001
    python generate_insight.py                               # proses SEMUA koperasi, periode terbaru
    python generate_insight.py --koperasi KDMP-00001          # satu koperasi saja

Output:
    ../data/output/sigap_kopdes.db   -> tabel ai_insight
    ../data/output/ai_insight.csv
"""
import os
import sys
import json
import time
import sqlite3
import argparse
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "..", "data", "output")
DB_PATH = os.path.join(DATA_DIR, "sigap_kopdes.db")

def _current_provider():
    """Dibaca fresh dari os.environ tiap dipanggil, supaya PUT /admin/ai-provider
    berlaku seketika di proses yang sedang jalan tanpa restart."""
    return os.environ.get("AI_PROVIDER", "anthropic").lower()


CLAUDE_MODEL_DEFAULT = "claude-haiku-4-5-20251001"  # ringan & murah, cukup untuk narasi terstruktur
GEMINI_MODEL_DEFAULT = "gemini-3.7-flash"  # per Agustus 2026 -- katalog model berubah dari waktu ke waktu
OLLAMA_MODEL_DEFAULT = "gemma4:cloud"  # model cloud Ollama, lihat https://ollama.com/library
MAX_TOKENS = 400

_MODEL_ENV_BY_PROVIDER = {
    "gemini": ("GEMINI_MODEL", GEMINI_MODEL_DEFAULT),
    "ollama": ("OLLAMA_MODEL", OLLAMA_MODEL_DEFAULT),
    "anthropic": ("CLAUDE_MODEL", CLAUDE_MODEL_DEFAULT),
}


def _model_candidates():
    """Daftar model untuk provider aktif, dicoba berurutan sebagai fallback
    chain (env var GEMINI_MODEL/CLAUDE_MODEL/OLLAMA_MODEL, dipisah koma).
    Id model tidak divalidasi di sini -- provider sendiri yang menolak."""
    env_name, default = _MODEL_ENV_BY_PROVIDER.get(_current_provider(), _MODEL_ENV_BY_PROVIDER["anthropic"])
    raw = os.environ.get(env_name, default)
    kandidat = [m.strip() for m in raw.split(",") if m.strip()]
    return kandidat or [default]

PROMPT_TEMPLATE = """Anda asisten analisis untuk PMO yang mengawasi Koperasi Desa/Kelurahan Merah Putih (KDMP) di Indonesia.

Data berikut SUDAH DIHITUNG oleh sistem untuk satu koperasi. JANGAN menghitung ulang, mengubah, atau menambah angka apa pun -- tugas Anda HANYA menarasikan dan menyarankan berdasarkan angka ini apa adanya:

Kondisi operasional koperasi (step 3-4):
- Nama: {nama}
- Wilayah: {desa_kelurahan}, {kabupaten_kota}, {provinsi}
- Skor kelayakan komposit: {skor_komposit}/100 (kategori: {kategori})
- Sub-skor -- Transaksi: {skor_transaksi}, Stok: {skor_stok}, Pelaporan: {skor_pelaporan}
- Perubahan dari bulan lalu: {delta_str} poin
- Proyeksi risiko kategori Kritis dalam 3 bulan: {prediksi_risiko_3bln}%

Profil wilayah -- simulasi struktur Indeks Desa Membangun/IDM (step 2), dipakai sebagai basis rekomendasi produk/promosi/program di bawah:
- Status kemajuan desa (IDM): {status_idm} (skor {skor_idm})
- Dimensi sosial/ekonomi/lingkungan (skala 0-1): {dimensi_sosial} / {dimensi_ekonomi} / {dimensi_lingkungan}
- Mata pencaharian dominan: {mata_pencaharian_dominan}
- Keragaman ekonomi wilayah: {ekonomi_beragam}
- Akses ke pusat perdagangan: {akses_pusat_perdagangan}

Balas HANYA dengan JSON persis format berikut, tanpa teks lain di luar JSON, tanpa markdown fence:
{{"narasi": "2-3 kalimat kondisi koperasi ini, sebutkan pola yang terlihat dari sub-skor (mis. merata rendah vs terkonsentrasi di satu indikator)", "rekomendasi_tindakan": "satu rekomendasi tindakan konkret untuk PMO terkait operasional koperasi", "produk_prioritas": ["2-3 ide produk/jasa konkret yang relevan dengan mata pencaharian dominan & keragaman ekonomi wilayah ini, masing-masing sebagai string singkat"], "rekomendasi_promosi": "satu ide kampanye/promosi konkret untuk koperasi ini, sebutkan momentum atau waktu yang paling tepat", "rekomendasi_program": ["2-3 ide program non-produk (pelatihan, kemitraan, digitalisasi, dst.) yang ditarik dari dimensi sosial/ekonomi/lingkungan & akses pasar wilayah, masing-masing sebagai string singkat"]}}"""


def load_context(koperasi_id=None, periode=None):
    conn = sqlite3.connect(DB_PATH)
    skor = pd.read_sql("SELECT * FROM skor_kelayakan", conn)
    koperasi = pd.read_sql("SELECT * FROM koperasi", conn)
    wilayah = pd.read_sql("SELECT * FROM wilayah", conn)
    profil = pd.read_sql("SELECT * FROM profil_wilayah", conn)
    conn.close()

    for c in ["skor_transaksi", "skor_stok", "skor_pelaporan", "skor_komposit"]:
        skor[c] = pd.to_numeric(skor[c])

    skor = skor.sort_values(["koperasi_id", "periode"])
    skor["delta"] = skor.groupby("koperasi_id")["skor_komposit"].diff().fillna(0)

    periode = periode or skor["periode"].max()
    df = skor[skor["periode"] == periode]
    if koperasi_id:
        df = df[df["koperasi_id"] == koperasi_id]
    if df.empty:
        return df

    return (
        df.merge(koperasi, on="koperasi_id")
          .merge(wilayah, on="kode_wilayah")
          .merge(profil, on="kode_wilayah")
    )


def build_prompt(row):
    delta = row["delta"]
    ekonomi_beragam = "Ya" if str(row["ekonomi_beragam"]) in ("1", "True", "true") else "Tidak"
    return PROMPT_TEMPLATE.format(
        nama=row["nama_koperasi"], desa_kelurahan=row["desa_kelurahan"],
        kabupaten_kota=row["kabupaten_kota"], provinsi=row["provinsi"],
        skor_komposit=row["skor_komposit"], kategori=row["kategori"],
        skor_transaksi=row["skor_transaksi"], skor_stok=row["skor_stok"],
        skor_pelaporan=row["skor_pelaporan"],
        delta_str=f"{delta:+.1f}",
        prediksi_risiko_3bln=row["prediksi_risiko_3bln"],
        status_idm=row["status_idm"], skor_idm=row["skor_idm"],
        dimensi_sosial=row["dimensi_sosial"], dimensi_ekonomi=row["dimensi_ekonomi"],
        dimensi_lingkungan=row["dimensi_lingkungan"],
        mata_pencaharian_dominan=row["mata_pencaharian_dominan"],
        ekonomi_beragam=ekonomi_beragam,
        akses_pusat_perdagangan=row["akses_pusat_perdagangan"],
    )


def _parse_json_reply(teks):
    """Provider kadang membungkus balasan dengan fence ```json walau sudah
    diminta tidak -- dibersihkan sebelum di-parse."""
    teks = teks.strip().replace("```json", "").replace("```", "").strip()
    return json.loads(teks)


def panggil_claude(prompt, client):
    kandidat = _model_candidates()
    errors = []
    for i, model in enumerate(kandidat):
        try:
            resp = client.messages.create(
                model=model,
                max_tokens=MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            )
            return _parse_json_reply(resp.content[0].text)
        except Exception as e:
            errors.append(f"{model}: {e}")
            if i < len(kandidat) - 1:
                continue
            raise RuntimeError("Semua model gagal dicoba -- " + " | ".join(errors)) from e


def panggil_gemini(prompt, client):
    kandidat = _model_candidates()
    errors = []
    for i, model in enumerate(kandidat):
        try:
            interaction = client.interactions.create(model=model, input=prompt)
            return _parse_json_reply(interaction.output_text)
        except Exception as e:
            errors.append(f"{model}: {e}")
            if i < len(kandidat) - 1:
                continue
            raise RuntimeError("Semua model gagal dicoba -- " + " | ".join(errors)) from e


def panggil_ollama(prompt, client):
    kandidat = _model_candidates()
    errors = []
    for i, model in enumerate(kandidat):
        try:
            resp = client.chat(model=model, messages=[{"role": "user", "content": prompt}])
            return _parse_json_reply(resp["message"]["content"])
        except Exception as e:
            errors.append(f"{model}: {e}")
            if i < len(kandidat) - 1:
                continue
            raise RuntimeError("Semua model gagal dicoba -- " + " | ".join(errors)) from e


def panggil_llm(prompt, client):
    provider = _current_provider()
    if provider == "gemini":
        return panggil_gemini(prompt, client)
    if provider == "ollama":
        return panggil_ollama(prompt, client)
    return panggil_claude(prompt, client)


LIST_FIELDS = ["produk_prioritas", "rekomendasi_program"]


def encode_list_fields(out):
    """SQLite tidak punya tipe list -- produk_prioritas & rekomendasi_program
    disimpan sebagai JSON array di kolom TEXT (diurai balik di api/main.py)."""
    for field in LIST_FIELDS:
        val = out.get(field, [])
        if isinstance(val, str):
            val = [val]
        out[field] = json.dumps(val, ensure_ascii=False)
    return out


def _table_exists(conn, name):
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def simpan(hasil_list):
    """UPSERT per (koperasi_id, periode) -- baris koperasi lain yang sudah
    tersimpan tetap dipertahankan, tidak ditimpa total."""
    if not hasil_list:
        print("Tidak ada hasil untuk disimpan.")
        return
    df_baru = pd.DataFrame(hasil_list)
    conn = sqlite3.connect(DB_PATH)
    if _table_exists(conn, "ai_insight"):
        df_lama = pd.read_sql("SELECT * FROM ai_insight", conn)
        kunci_baru = set(zip(df_baru["koperasi_id"], df_baru["periode"]))
        tertimpa = df_lama.apply(lambda r: (r["koperasi_id"], r["periode"]) in kunci_baru, axis=1)
        df_gabungan = pd.concat([df_lama[~tertimpa], df_baru], ignore_index=True)
    else:
        df_gabungan = df_baru
    df_gabungan.to_sql("ai_insight", conn, if_exists="replace", index=False)
    conn.close()
    df_gabungan.to_csv(os.path.join(DATA_DIR, "ai_insight.csv"), index=False)
    print(f"Tersimpan: {len(df_baru)} insight baru/update -> tabel ai_insight ({len(df_gabungan)} baris total, db + csv)")


def build_client():
    """Client untuk provider aktif (AI_PROVIDER). Melempar RuntimeError
    (bukan sys.exit) kalau API key belum di-set, supaya pemanggil (CLI atau
    endpoint /insight/{id}) bisa menanganinya masing-masing."""
    if _current_provider() == "gemini":
        if not os.environ.get("GEMINI_API_KEY"):
            raise RuntimeError(
                "GEMINI_API_KEY belum di-set di environment. "
                "Dapatkan API key gratis di https://aistudio.google.com/apikey lalu export GEMINI_API_KEY=..."
            )
        from google import genai
        return genai.Client()  # baca GEMINI_API_KEY dari environment otomatis
    elif _current_provider() == "ollama":
        if not os.environ.get("OLLAMA_API_KEY"):
            raise RuntimeError(
                "OLLAMA_API_KEY belum di-set di environment. Dapatkan API key di "
                "https://ollama.com/settings/keys lalu export OLLAMA_API_KEY=..."
            )
        import ollama
        # Default ke Ollama Cloud, bukan server lokal; OLLAMA_HOST bisa dioverride.
        host = os.environ.get("OLLAMA_HOST", "https://ollama.com")
        return ollama.Client(host=host, headers={"Authorization": f"Bearer {os.environ['OLLAMA_API_KEY']}"})
    else:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError(
                "ANTHROPIC_API_KEY belum di-set di environment. export ANTHROPIC_API_KEY=sk-ant-... "
                "(atau set AI_PROVIDER=gemini untuk pakai Gemini gratis)."
            )
        import anthropic
        return anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def generate_one(row, client):
    """Generate & encode satu insight (belum disimpan) dari satu baris
    load_context(). Dipakai baik oleh main() maupun endpoint /insight/{id}."""
    prompt = build_prompt(row)
    out = panggil_llm(prompt, client)
    out = encode_list_fields(out)
    out["koperasi_id"] = row["koperasi_id"]
    out["periode"] = row["periode"]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--koperasi", help="Proses satu koperasi_id saja, mis. KDMP-00001")
    ap.add_argument("--dry-run", action="store_true", help="Cetak prompt & uji alur data tanpa memanggil API")
    args = ap.parse_args()

    df = load_context(koperasi_id=args.koperasi)
    if df.empty:
        print("Tidak ada baris yang cocok -- cek koperasi_id atau jalankan step 2-4 dulu.")
        sys.exit(1)

    if args.dry_run:
        contoh = build_prompt(df.iloc[0])
        print("=" * 70)
        print(f"CONTOH PROMPT (koperasi 1 dari {len(df)}):")
        print("=" * 70)
        print(contoh)
        print("=" * 70)
        print(f"\n[dry-run] {len(df)} koperasi akan diproses kalau dijalankan tanpa --dry-run.")
        print(f"Provider aktif: {_current_provider()} (ganti lewat env var AI_PROVIDER=anthropic|gemini|ollama).")
        print("Data & prompt di atas valid -- tinggal set API key providernya untuk jalan sungguhan.")
        return

    try:
        client = build_client()
    except RuntimeError as e:
        print(str(e))
        print("Atau jalankan dengan --dry-run untuk melihat prompt tanpa memanggil API.")
        sys.exit(1)

    hasil = []
    for _, row in df.iterrows():
        try:
            out = generate_one(row, client)
            hasil.append(out)
            print(f"OK    {row['koperasi_id']}  {row['nama_koperasi']}")
        except Exception as e:
            print(f"GAGAL {row['koperasi_id']}: {e}")
        time.sleep(0.3)  # jaga rate limit kalau memproses banyak koperasi sekaligus

    simpan(hasil)
    print(f"\n{len(hasil)}/{len(df)} insight berhasil dibuat.")


if __name__ == "__main__":
    main()
