import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import tailwindcss from "@tailwindcss/vite";
import { resolve } from "path";

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  base: "/static/",
  resolve: {
    alias: {
      "@": resolve(__dirname, "src"),
    },
  },
  server: {
    port: 5720,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:7800",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: resolve(__dirname, "../backend/app/web/static"),
    emptyOutDir: true,
    sourcemap: false,
  },
});
