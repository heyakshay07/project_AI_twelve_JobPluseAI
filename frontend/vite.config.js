import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In Docker the API lives at http://backend:8000; locally it is http://localhost:8000
const apiTarget = process.env.VITE_API_PROXY || "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: { host: true, port: 5173, allowedHosts: ["project-ai-twelve-jobpluseai.onrender.com"],
proxy: { "/api": { target: apiTarget, changeOrigin: true } } },
});

