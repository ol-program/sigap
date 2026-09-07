import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Port & allowedHosts BEDA dari frontend/ (5173) SENGAJA -- app ini portal
// superadmin terpisah (lihat README bagian "Portal Superadmin"), bukan
// bagian dari dashboard utama. *.localhost otomatis resolve ke 127.0.0.1 di
// browser/OS modern (RFC 6761) tanpa perlu edit /etc/hosts, jadi
// http://admin.localhost:5174 sudah bisa dipakai sekarang untuk mensimulasikan
// subdomain terpisah di lokal -- di produksi ini jadi subdomain sungguhan
// (mis. admin.domain-anda.com) lewat deployment terpisah dari frontend/.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    allowedHosts: ["localhost", "admin.localhost"],
  },
});
