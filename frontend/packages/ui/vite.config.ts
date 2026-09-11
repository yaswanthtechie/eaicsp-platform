import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { resolve } from "path";

export default defineConfig({
  plugins: [react()],

  build: {
    lib: {
      entry: resolve(import.meta.dirname, "src/index.ts"),
      name: "EaicspUI",
      fileName: "index",
      formats: ["es"],
    },

    rollupOptions: {
      external: [
        "react",
        "react-dom",
        "react/jsx-runtime",
        "react-hook-form",
        "@hookform/resolvers",
        "recharts",
        "zod",
      ],

      output: {
        format: "es",
        exports: "named",
      },
    },
  },

  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/setupTests.ts",
  },
});
