import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: '/api/agentx/',
  build: {
    outDir: '../dist/agentx_web',
    emptyOutDir: true,
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8188',
        changeOrigin: true,
        // Remove origin header to bypass ComfyUI CORS protection
        configure: (proxy) => {
          proxy.on('proxyReq', (proxyReq) => {
            proxyReq.removeHeader('origin');
          });
        }
      }
    }
  }
})
