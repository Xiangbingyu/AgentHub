# 命令参考

## 开发环境

```bash
npm run dev              # 启动开发服务器 (默认端口 5173)
npm run dev:test         # test环境开发
npm run dev:pre         # pre环境开发
npm run dev:prod        # 生产环境开发
```

## 构建

```bash
npm run build            # 构建生产版本
npm run build:test      # 测试环境构建
npm run build:pre       # 预发布构建
npm run build:prod      # 生产环境构建
npm run preview         # 预览构建结果
```

## 代码检查

```bash
npm run lint            # ESLint检查
npm run lint:fix        # ESLint自动修复
npm run typecheck       # TypeScript类型检查
npm run lint:style      # CSS样式检查
```

## 工具

```bash
npm run preview         # 本地预览构建产物
npm run clean           # 清理node_modules和构建产物
```
