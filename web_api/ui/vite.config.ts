import path from "path"
import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"

export default defineConfig({
  plugins: [react()],
  // Base path for all assets - must match the static file serving path
  base: "/static/dist/",
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    outDir: "../static/dist",
    emptyOutDir: true,
    manifest: true,
    // Enable minification for smaller bundles
    minify: 'esbuild',
    // Target modern browsers for smaller output
    target: 'es2020',
    // Warn only for chunks > 300KB
    chunkSizeWarningLimit: 300,
    rollupOptions: {
      input: "./src/main.tsx",
      output: {
        // Use fixed names for easy integration (no need for manifest parsing)
        entryFileNames: "assets/main.js",
        chunkFileNames: "assets/[name].js",
        assetFileNames: "assets/[name].[ext]",
        // Manual chunks to split large dependencies
        manualChunks: {
          // React core
          'vendor-react': ['react', 'react-dom'],
          // Charts library (large)
          'vendor-recharts': ['recharts'],
          // Animation library
          'vendor-motion': ['framer-motion'],
          // UI components (Radix)
          'vendor-radix': [
            '@radix-ui/react-avatar',
            '@radix-ui/react-dialog',
            '@radix-ui/react-dropdown-menu',
            '@radix-ui/react-label',
            '@radix-ui/react-popover',
            '@radix-ui/react-select',
            '@radix-ui/react-slot',
            '@radix-ui/react-switch',
            '@radix-ui/react-tooltip',
          ],
          // i18n
          'vendor-i18n': ['i18next', 'react-i18next'],
          // Icons
          'vendor-icons': ['lucide-react'],
          // Utilities
          'vendor-utils': ['clsx', 'tailwind-merge', 'class-variance-authority', 'date-fns'],
        },
      },
    },
    sourcemap: false,
  },
  optimizeDeps: {
    include: [
      'react',
      'react-dom',
      'recharts',
      'framer-motion',
      'lucide-react',
      'i18next',
      'react-i18next',
    ],
  },
})
