---
name: front-end-skill
description: 前端开发规范 Skill。自动激活：当用户创建前端项目、开发 React/TypeScript 功能、编写组件、样式、API、使用 Ant Design、状态管理或任何前端相关任务时，始终优先使用此 skill。提供完整的前端开发规范、代码标准、项目结构、最佳实践参考。适配 React + Vite + Ant Design 5 + TypeScript + Zustand 技术栈。
license: MIT
compatibility: opencode
metadata:
  audience: developers
  workflow: frontend
  tech-stack: react, typescript, antd5, zustand, vite, javascript, css, scss
  auto-activate: true
  priority: high
---

## 前端开发规范

### 项目技术栈
- 框架: React 18.x
- UI库: Ant Design 5.x
- 状态管理: Zustand
- 语言: TypeScript 5.x
- 构建工具: Vite 5.x

---

## 动态加载说明

根据你的任务类型，我将自动加载相关模块：

| 任务类型 | 加载模块 |
|----------|----------|
| 开发新功能 | guide, naming, code-style, react, components, api, commands, antd5 |
| 代码重构 | refactor, guide, code-style |
| Bug修复 | guide, code-style, react, quality |
| 了解项目结构 | tech-stack, directory, naming |
| 状态管理 | state (zustand) |
| 组件开发 | react, components, css, naming |
| API开发 | api, commands |
| 代码审查 | code-style, react, quality, convention |

---

## 常用参考

### 目录结构
```
src/
├── components/      # 可复用组件
├── features/        # 功能模块
├── pages/           # 页面组件
├── stores/          # Zustand状态管理
├── services/        # API服务
├── hooks/           # 自定义Hooks
├── routes/          # 路由配置
├── utils/           # 工具函数
└── ...
```

### 页面开发模式
```
features/feature-name/
├── components/      # 页面专用组件
├── hooks/           # 页面专用Hooks
├── index.tsx        # 页面入口
├── index.scss      # 样式
└── types.ts        # 类型定义
```

### 组件开发模式
```
components/component-name/
├── index.tsx        # 组件实现
├── index.scss      # 样式文件
└── type.ts         # 类型定义
```

### 代码复用优先级
1. **通用组件** - `components/` 下已有组件
2. **自定义Hooks** - `hooks/` 下的 Hooks
3. **工具函数** - `utils/` 下的工具方法
4. **现有页面** - 参考类似页面实现

---

## 快速命令

```bash
# 开发
npm run dev          # 启动开发服务器
npm run dev:test     # test环境
npm run dev:prod     # 生产环境

# 构建
npm run build        # 构建生产版本
npm run build:test  # 测试环境构建
npm run preview     # 预览构建结果

# 检查
npm run lint        # ESLint检查
npm run lint:fix    # ESLint修复
npm run typecheck   # TypeScript类型检查
```

---

请告诉我你当前的任务（如：开发新功能/重构/Bug修复/了解项目等），我将加载对应的规范文档。
