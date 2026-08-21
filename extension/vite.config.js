import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'dist',
    // Don't clear dist (we have public/ files there too)
    emptyOutDir: true,
  },
});
