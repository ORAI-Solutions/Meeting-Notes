import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: '127.0.0.1',
    proxy: {
      '/meetings': { target: 'http://127.0.0.1:5174', changeOrigin: true },
      '/devices': { target: 'http://127.0.0.1:5174', changeOrigin: true },
      '/settings': { target: 'http://127.0.0.1:5174', changeOrigin: true },
      '/search': { target: 'http://127.0.0.1:5174', changeOrigin: true },
      '/ws': { target: 'ws://127.0.0.1:5174', ws: true },
    },
  },
});


