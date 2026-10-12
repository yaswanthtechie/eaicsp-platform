/// <reference types="vitest/config" />
import { colors } from "./src/tokens.ts";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { VitePWA } from "vite-plugin-pwa";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { graphqlMockServer } from "./src/mock-server/graphqlMockPlugin.ts";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    graphqlMockServer(),
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
            src: "/pwa-192x192.png",
            sizes: "192x192",
            type: "image/png",
          },
          {
            src: "/pwa-512x512.png",
            sizes: "512x512",
            type: "image/png",
          },
          {
            src: "/maskable-icon-512x512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "maskable",
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
    env: {
      VITE_USE_MOCK_AUTH: "true",
    },
  },

  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
    dedupe: ["react", "react-dom"],
  },

  server: {
    proxy: {
      "/api/v1/auth": {
        target: "http://localhost:8005",
        changeOrigin: true,
      },
    },
  },
});