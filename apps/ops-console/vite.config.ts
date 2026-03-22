import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const opsConsolePort = Number(process.env.OPS_CONSOLE_PORT ?? 3000);

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: opsConsolePort,
    proxy: {
      "/api/orchestrator": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/orchestrator/, ""),
      },
      "/api/control-plane": {
        target: "http://127.0.0.1:8008",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/control-plane/, ""),
      },
    },
  },
});
