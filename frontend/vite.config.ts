import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig(({ mode }) => {
  const demo = mode === "demo";
  return {
    base: demo ? "/folionym-pdf/" : "/",
    plugins: [react()],
    build: {
      outDir: demo ? "../dist-demo" : "../src/folionym/web_dist",
      emptyOutDir: true,
      sourcemap: false,
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
