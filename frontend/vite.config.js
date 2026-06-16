import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // 前端统一走同源 /api，开发期由 Vite 代理到 gateway_service。
      // 用 127.0.0.1 而非 localhost：Node 解析 localhost 会先试 IPv6(::1)，
      // 而 uvicorn 默认只监听 IPv4，导致 ECONNREFUSED（SSE 长连接尤为明显）。
      '/api': {
        target: 'http://127.0.0.1:8080',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
