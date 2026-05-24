# Vite 配置

## 基础配置

```ts
// vite.config.ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { resolve } from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:3000',
        changeOrigin: true,
      },
    },
  },
});
```

## 环境变量

```ts
// .env
VITE_APP_TITLE=管理后台
VITE_API_BASE_URL=/api

// .env.development
VITE_API_BASE_URL=/api

// .env.production
VITE_API_BASE_URL=https://api.example.com
```

使用方式：
```ts
import.meta.env.VITE_API_BASE_URL
```

## 构建优化

### 拆包配置

```ts
export default defineConfig({
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor-react': ['react', 'react-dom'],
          'vendor-antd': ['antd'],
        },
      },
    },
  },
});
```

### Gzip 压缩

```bash
npm install vite-plugin-compression -D
```

```ts
import compression from 'vite-plugin-compression';

export default defineConfig({
  plugins: [
    compression(),
  ],
});
```

## 常用插件

| 插件 | 用途 |
|------|------|
| @vitejs/plugin-react | React 支持 |
| vite-plugin-compression | Gzip 压缩 |
| vite-plugin-imagemin | 图片压缩 |
| @vitejs/plugin-react-swc | 使用 SWC 加速 |

## 开发服务器

```bash
# 默认开发
npm run dev

# 指定端口
npm run dev -- --port 3000

# 指定主机
npm run dev -- --host 0.0.0.0
```
