import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// Backend URL for the dev proxy. Defaults to 8010 (scripts/demo.sh); override with PAPERPILOT_API_URL.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", ["VITE_", "PAPERPILOT_"]);
  const target = env.PAPERPILOT_API_URL || "http://127.0.0.1:8010";
  return {
    plugins: [react()],
    server: {
      port: 5173,
      host: true,
      proxy: {
        "/api": { target, changeOrigin: true },
      },
    },
    build: {
      outDir: "dist",
      sourcemap: false,
    },
  };
});
