import { fileURLToPath, URL } from "node:url";

import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vite";

// The Python backend that serves the API + media during local development.
const BACKEND = process.env.KIOSK_BACKEND ?? "http://127.0.0.1:8000";
const backendProxy = { target: BACKEND, changeOrigin: true };

// Build output goes straight into the FastAPI static dir next to the (still
// committed) "Classic" SPA. emptyOutDir MUST stay false so we never wipe
// assets/, icons/, favicon.ico or index.html that belong to Classic.
// `--mode demo` (pnpm build:demo) instead builds the backend-less public demo into dist/ for Vercel.
export default defineConfig(({ mode }) => ({
  plugins: [vue()],
  base: "/",
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  build: {
    outDir: fileURLToPath(new URL(mode === "demo" ? "./dist" : "../src/web/frontend", import.meta.url)),
    emptyOutDir: mode === "demo",
    rollupOptions: {
      // the admin dashboard needs the backend, so the public demo only ships the kiosk
      input: Object.fromEntries(
        (mode === "demo" ? ["framebooth"] : ["framebooth", "admin"]).map((name) => [
          name,
          fileURLToPath(new URL(`./${name}.html`, import.meta.url)),
        ]),
      ),
      output: {
        entryFileNames: "kiosk/[name]-[hash].js",
        chunkFileNames: "kiosk/[name]-[hash].js",
        assetFileNames: "kiosk/[name]-[hash][extname]",
      },
    },
  },
  server: {
    port: 5273,
    proxy: {
      "/api": backendProxy,
      "/media": backendProxy,
      "/gallery": backendProxy,
      "/userdata": backendProxy,
      "/private.css": backendProxy,
    },
  },
}));
