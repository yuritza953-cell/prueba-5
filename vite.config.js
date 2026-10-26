import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// En desarrollo el servidor de Vite hace proxy de /api al servidor de Python
// (server.py, puerto 8000). En produccion server.py sirve ./dist y /api/search.
export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      // La app y las dos páginas legales se compilan como documentos separados:
      // cada una tiene su propio HTML, CSS y entrada JSX.
      input: {
        main: 'index.html',
        terms: 'terms.html',
        privacy: 'privacy.html'
      }
    }
  },
  server: {
    proxy: {
      '/api': 'http://localhost:8000'
    }
  }
});
