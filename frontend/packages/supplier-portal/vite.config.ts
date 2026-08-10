import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),

    VitePWA({
      registerType: "autoUpdate",

      includeAssets: [
        "favicon.ico",
        "pwa-192.png",
        "pwa-512.png",
      ],

      workbox: {
        globPatterns: [
          "**/*.{js,css,html,ico,png,svg,woff2}",
        ],
      },

      manifest: {
        name: "Supplier Portal",
        short_name: "Supplier",
        description: "Supplier Portal GraphQL App",

        theme_color: "#0B0F1A",
        background_color: "#0B0F1A",

        display: "standalone",
        start_url: "/",

        icons: [
          {
            src: "pwa-192.png",
            sizes: "192x192",
            type: "image/png",
          },
          {
            src: "pwa-512.png",
            sizes: "512x512",
            type: "image/png",
          },
        ],
      },
    }),
  ],
});