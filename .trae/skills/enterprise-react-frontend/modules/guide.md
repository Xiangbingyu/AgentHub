# 开发指南

## 概述

前端开发规范，基于 React + TypeScript + Ant Design 5 + Zustand + Vite

## 如何查找参考示例

### 1. 查找类似页面
- 先在 `features/` 或 `pages/` 目录下搜索相同类型的页面
- 例如：开发订单相关功能 → 参考 `features/order/` 或 `pages/order/`

### 2. 查找类似组件
- 在 `components/` 目录下查找是否有可复用的组件
- 使用 grep 搜索相关关键词

### 3. 查找API调用
- 参考同模块的 `services/api.ts` 文件
- 查看 `services/` 了解请求封装方式

### 4. 查找状态管理
- 在 `stores/` 下查找类似的状态管理

## 页面开发模式

```
features/user/
├── components/      # 页面专用组件
│   ├── UserForm.tsx
│   └── UserTable.tsx
├── hooks/           # 页面专用Hooks
├── services/        # 页面API
├── types.ts         # 类型定义
├── UserList.tsx     # 列表页面
└── index.scss       # 样式
```

## 组件开发模式

```
components/Loading/
├── index.tsx        # 组件实现
├── index.scss       # 样式文件
└── type.ts          # 类型定义
```

## 开发流程

1. **先搜索** - 在项目中查找类似功能的实现
2. **再复用** - 优先使用已有的通用组件和 Hooks
3. **参考模式** - 按照项目现有的代码模式编写
4. **检查规范** - 确保符合 ESLint 和 TypeScript 规则

## 常用目录参考

| 功能 | 参考目录 |
|------|----------|
| 列表页面 | `features/order/`、`pages/order/` |
| 表单页面 | `features/user/` |
| 弹窗/抽屉 | `features/xxx/components/` |
| 状态管理 | `stores/useXxxStore.ts` |
| API封装 | `features/xxx/services/api.ts` |

## 代码复用优先级

1. **通用组件** - `components/` 下已有组件优先使用
2. **自定义Hooks** - `hooks/` 下的 Hooks
3. **工具函数** - `utils/` 下的工具方法
4. **现有页面** - 参考类似页面实现
