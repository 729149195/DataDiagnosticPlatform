import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    vue(),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      '*': fileURLToPath(new URL('./public', import.meta.url))
    },
  },
  server:{
    host: '0.0.0.0',
    port: 5173,
    https: {
      key: './10.1.108.19+3-key.pem',  // 私钥路径
      cert: './10.1.108.19+3.pem'      // 证书路径
    }
  },
  worker: {
    format: 'es',
    plugins: []
  },
  optimizeDeps: {
    exclude: ['d3']
  }
})
