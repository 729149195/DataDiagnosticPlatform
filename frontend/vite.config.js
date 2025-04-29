import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import fs from 'fs'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    vue({
      template: {
        compilerOptions: {
          // 减少编译警告
          whitespace: 'condense'
        }
      }
    }),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      '*': fileURLToPath(new URL('./public', import.meta.url))
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    https: {
      key: fs.readFileSync(path.resolve(__dirname, '10.1.108.231-key.pem')),
      cert: fs.readFileSync(path.resolve(__dirname, '10.1.108.231.pem')),
    },
    cors: {
      origin: '*',
      methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
      allowedHeaders: ['Content-Type', 'Authorization'],
      credentials: true
    },
    headers: {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization'
    }
  },
  worker: {
    format: 'es',
    plugins: () => [myPlugin()]
  },
  optimizeDeps: {
    exclude: ['d3']
  },
  build: {
    // 性能优化选项
    minify: 'terser',
    terserOptions: {
      compress: {
        // 移除控制台日志和警告
        drop_console: true,
        drop_debugger: true
      }
    },
    // 分割代码块以提高性能
    rollupOptions: {
      output: {
        manualChunks: {
          'highcharts': ['highcharts'],
          'd3': ['d3'],
          'vue-vendor': ['vue', 'vue-router', 'vuex'],
          'element-plus': ['element-plus']
        }
      }
    }
  }
})
