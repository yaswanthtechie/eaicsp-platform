/// <reference types="vitest/config" />
import { colors } from "./src/tokens.ts";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { VitePWA } from "vite-plugin-pwa";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: "autoUpdate",
      manifest: {
        name: "Executive Dashboard",
        short_name: "Dashboard",
        description: "Executive supply chain dashboard",
        start_url: "/",
        display: "standalone",
        background_color: colors.bg,
        theme_color: colors.primary,
        icons: [
          {
            src: "/icons/pwa-icon.png",
            sizes: "192x192",
            type: "image/png",
          },
          {
            src: "/icons/pwa-icon2.png",
            sizes: "512x512",
            type: "image/png",
          },
        ],
      },
    }),
  ],

  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    testTimeout: 15000,
    exclude: ["**/e2e/**", "**/node_modules/**"],
  },

  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
    dedupe: ["react", "react-dom"],
  },
});