import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
    plugins: [react()],
    resolve: {
        alias: {
            "@": path.resolve(__dirname, "./src"),
        },
    },
    server: {
        proxy: {
            '/api': {
                target: 'http://127.0.0.1:8000',
                changeOrigin: true,
            },
            '/ws': {
                target: 'ws://127.0.0.1:8000',
                ws: true,
                changeOrigin: true,
                configure: (proxy) => {
                    // 说明：后端重启/前端刷新时，ws 连接会被关闭；Vite 代理偶尔会打印 EPIPE。
                    // 这里忽略常见的断连错误，避免控制台刷屏。
                    proxy.on('error', (err) => {
                        if (err?.code === 'EPIPE' || err?.code === 'ECONNRESET') return
                        console.warn('[vite] ws proxy error:', err)
                    })
                },
            }
        }
    }
})
