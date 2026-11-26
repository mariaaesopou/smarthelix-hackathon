import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    watch: { usePolling: process.env.VITE_WATCH_POLLING === "true" },
    proxy: {
      "/api": { target: "http://api:3000", rewrite: (p) => p.replace(/^\/api/, "") },
    },
  },
});
