import { useEffect, useState } from "react";
import { api } from "../api.js";

export default function AiKeyCard() {
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(null);
  const [apiKey, setApiKey] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const [providerChoice, setProviderChoice] = useState("anthropic");
  const [providerError, setProviderError] = useState(null);
  const [savingProvider, setSavingProvider] = useState(false);

  const [modelChoice, setModelChoice] = useState("");
  const [modelError, setModelError] = useState(null);
  const [savingModel, setSavingModel] = useState(false);

  const load = () => {
    setError(null);
    api.getAiKey().then((res) => {
      setStatus(res);
      setProviderChoice(res.provider);
      setModelChoice(res.model);
    }).catch((e) => setError(e.message));
  };

  useEffect(load, []);

  const handleSubmitKey = async (e) => {
    e.preventDefault();
    setError(null);
    setSaved(false);
    setSaving(true);
    try {
      await api.setAiKey(apiKey);
      setApiKey("");
      setSaved(true);
      load();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleSubmitProvider = async (e) => {
    e.preventDefault();
    setProviderError(null);
    setSavingProvider(true);
    try {
      await api.setAiProvider(providerChoice);
      load();
    } catch (err) {
      setProviderError(err.message);
    } finally {
      setSavingProvider(false);
    }
  };

  const handleSubmitModel = async (e) => {
    e.preventDefault();
    setModelError(null);
    setSavingModel(true);
    try {
      await api.setAiModel(modelChoice);
      load();
    } catch (err) {
      setModelError(err.message);
    } finally {
      setSavingModel(false);
    }
  };

  return (
    <div className="card" style={{ marginBottom: 20 }}>
      <h3 style={{ marginTop: 0 }}>AI Insight -- Provider &amp; API Key</h3>
      <p className="page-desc">
        Dipakai backend untuk menghasilkan narasi &amp; rekomendasi AI Insight (lihat halaman Detail Koperasi di
        dashboard utama). Perubahan di sini langsung berlaku tanpa perlu restart server, dan tersimpan permanen
        (tidak hilang saat server di-restart).
      </p>

      <form onSubmit={handleSubmitProvider} className="form-field" style={{ display: "flex", gap: 8, alignItems: "flex-end" }}>
        <div style={{ flex: 1 }}>
          <label>Provider AI aktif</label>
          <select value={providerChoice} onChange={(e) => setProviderChoice(e.target.value)}>
            <option value="anthropic">Anthropic (Claude)</option>
            <option value="gemini">Google Gemini</option>
            <option value="ollama">Ollama Cloud</option>
          </select>
        </div>
        <button type="submit" className="btn" disabled={savingProvider || providerChoice === status?.provider}>
          {savingProvider ? "Mengganti..." : "Ganti Provider"}
        </button>
      </form>
      {providerError && <div className="error-state" style={{ padding: "8px 0", textAlign: "left" }}>{providerError}</div>}

      {status && (
        <p style={{ fontSize: 13, color: "var(--text-secondary)", margin: "12px 0" }}>
          Provider aktif sekarang: <strong>{status.provider}</strong> ({status.env_name}) --{" "}
          {status.is_set ? (
            <span className="badge-ok">Terpasang ({status.masked})</span>
          ) : (
            <span className="badge-warn">Belum diset</span>
          )}
        </p>
      )}

      <form onSubmit={handleSubmitModel} className="form-field" style={{ display: "flex", gap: 8, alignItems: "flex-end" }}>
        <div style={{ flex: 1 }}>
          <label>Id model untuk provider aktif ({status?.model_env_name || "..."})</label>
          <input
            type="text"
            value={modelChoice}
            onChange={(e) => setModelChoice(e.target.value)}
            placeholder={status?.model_default}
          />
          <div className="field-hint">
            Isi persis sesuai id model dari dokumentasi provider. Bisa isi LEBIH DARI SATU dipisah koma, mis.{" "}
            <code>gemini-3.5-flash, gemini-2.5-flash, gemma-4-31b-it</code> -- dicoba BERURUTAN sebagai fallback
            (kalau model pertama gagal, mis. kuota habis atau model belum tersedia, otomatis coba yang
            berikutnya). Id-id ini TIDAK diverifikasi di sini, kalau semuanya salah/tidak ada provider yang akan
            menolaknya saat generate insight. Default kalau dikosongkan: <code>{status?.model_default}</code>.
          </div>
        </div>
        <button type="submit" className="btn" disabled={savingModel}>
          {savingModel ? "Mengganti..." : "Ganti Model"}
        </button>
      </form>
      {modelError && <div className="error-state" style={{ padding: "8px 0", textAlign: "left" }}>{modelError}</div>}

      <form onSubmit={handleSubmitKey}>
        <div className="form-field">
          <label>API key untuk provider aktif ({status?.env_name || "..."})</label>
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder={
              status?.env_name === "GEMINI_API_KEY" ? "AIza..." :
              status?.env_name === "OLLAMA_API_KEY" ? "(dari ollama.com/settings/keys)" :
              "sk-ant-..."
            }
            required
          />
          <div className="field-hint">
            Key ini berlaku untuk provider yang sedang aktif di atas -- kalau ganti provider, key untuk provider itu
            perlu diisi terpisah (masing-masing provider punya API key sendiri, tidak saling menggantikan).
          </div>
        </div>

        {error && <div className="error-state" style={{ padding: "8px 0", textAlign: "left" }}>{error}</div>}
        {saved && !error && (
          <p style={{ fontSize: 12, color: "var(--status-good)", marginBottom: 8 }}>API key tersimpan.</p>
        )}

        <button type="submit" className="btn btn-primary" disabled={saving}>
          {saving ? "Menyimpan..." : "Simpan API Key"}
        </button>
      </form>
    </div>
  );
}
