# 目录结构

## 推荐目录结构 (Feature-based)

```
src/
├── assets/             # 静态资源
│   ├── images/        # 图片
│   └── icons/         # 图标
├── components/        # 通用组件 (可被多个feature复用)
│   ├── common/        # 基础组件
│   └── business/      # 业务组件
├── features/          # 功能模块 (按业务功能划分)
│   ├── feature-a/
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── services/
│   │   ├── types.ts
│   │   └── index.tsx
│   └── feature-b/
├── hooks/             # 全局自定义Hooks
├── layouts/           # 布局组件
├── pages/             # 页面入口 (路由对应)
├── routes/            # 路由配置
├── services/          # API服务 (全局)
├── stores/            # Zustand状态管理
│   ├── index.ts       # store入口
│   └── useXxxStore.ts # 状态定义
├── styles/            # 全局样式
├── types/             # 全局类型定义
├── utils/             # 工具函数
├── App.tsx            # 根组件
└── main.tsx           # 入口文件
```

## 传统目录结构 (按类型划分)

```
src/
├── components/      # 可复用组件
├── pages/           # 页面组件
├── stores/          # Zustand状态管理
├── services/        # API服务
├── utils/           # 工具函数
├── hooks/           # 自定义Hooks
├── routes/          # 路由配置
├── styles/          # 全局样式
└── types/           # 类型定义
```

## 页面开发模式

```
features/user/
├── components/      # 页面专用组件
│   ├── UserForm.tsx
│   └── UserTable.tsx
├── hooks/           # 页面专用Hooks
│   └── useUserList.ts
├── services/        # 页面API
│   └── api.ts
├── types.ts         # 类型定义
├── UserList.tsx     # 列表页面
├── UserDetail.tsx   # 详情页面
└── index.scss       # 样式
```

## 组件开发模式

```
components/Loading/
├── index.tsx        # 组件实现
├── index.scss      # 样式文件
└── type.ts         # 类型定义
```
