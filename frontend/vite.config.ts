import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig(({ mode }) => ({
  plugins: [react(), tailwindcss()],
  base: mode === "demo" ? "/Agentic-Code-Review-Sandbox/" : "/",
  define: { __DEMO__: JSON.stringify(mode === "demo") },
  server: { proxy: { "/api": "http://127.0.0.1:8000" } },
}));
