import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";

// Output goes into the Django static tree so collectstatic can ship it.
const OUT_DIR = resolve(__dirname, "../../backend/static/dist/scheduling");

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: OUT_DIR,
    emptyOutDir: true,
    rollupOptions: {
      input: resolve(__dirname, "src/main.tsx"),
      output: {
        entryFileNames: "main.js",
        chunkFileNames: "[name]-[hash].js",
        assetFileNames: "[name]-[hash][extname]",
      },
    },
    target: "es2020",
    sourcemap: false,
  },
  server: {
    port: 5174,
  },
});
