import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig(({ mode }) => {
  const demo = mode === "demo";
  return {
    base: demo ? "/folionym-pdf/" : "/",
    plugins: [react()],
    // Demo-only static files (sample thumbnails) never reach the packaged app.
    publicDir: demo ? "demo-public" : false,
    build: {
      outDir: demo ? "../dist-demo" : "../src/folionym/web_dist",
      emptyOutDir: true,
      sourcemap: false,
      // The landing page ships with the static demo only; the packaged app
      // keeps its single index.html entry.
      ...(demo ? { rolldownOptions: { input: { index: "index.html", tour: "tour.html" } } } : {}),
    },
    server: {
      host: "127.0.0.1",
      port: 5173,
      proxy: {
        "/api": "http://127.0.0.1:8765",
      },
    },
  };
});
