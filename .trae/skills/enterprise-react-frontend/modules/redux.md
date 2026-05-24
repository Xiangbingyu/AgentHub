# 状态管理 (Zustand)

Zustand 是一个轻量级的状态管理方案，API 简洁。

## 目录结构

```
stores/
├── index.ts       # store入口，导出所有store
├── useAppStore.ts # 应用级状态
└── useUserStore.ts # 用户状态
```

## 基本使用

### 定义 Store

```ts
// stores/useAppStore.ts
import { create } from 'zustand';

interface AppState {
  collapsed: boolean;
  userInfo: Record<string, unknown>;
  setCollapsed: (collapsed: boolean) => void;
  setUserInfo: (userInfo: Record<string, unknown>) => void;
}

export const useAppStore = create<AppState>((set) => ({
  collapsed: false,
  userInfo: {},
  setCollapsed: (collapsed) => set({ collapsed }),
  setUserInfo: (userInfo) => set({ userInfo }),
}));
```

### 组件中使用

```tsx
import { useAppStore } from '@/stores/useAppStore';

const MyComponent = () => {
  const { collapsed, setCollapsed } = useAppStore();
  return (
    <button onClick={() => setCollapsed(!collapsed)}>
      {collapsed ? '展开' : '收起'}
    </button>
  );
};
```

## 异步操作

```ts
// stores/useUserStore.ts
import { create } from 'zustand';
import { fetchUserInfo } from '@/services/api';

interface UserState {
  userInfo: Record<string, unknown> | null;
  loading: boolean;
  fetchUser: () => Promise<void>;
}

export const useUserStore = create<UserState>((set) => ({
  userInfo: null,
  loading: false,
  fetchUser: async () => {
    set({ loading: true });
    try {
      const data = await fetchUserInfo();
      set({ userInfo: data, loading: false });
    } catch (error) {
      set({ loading: false });
    }
  },
}));
```

## 派生状态 (Selectors)

```tsx
// 基础选择器
const count = useStore((state) => state.count);

// 精细选择器 (避免不必要渲染)
const { name, age } = useStore((state) => ({
  name: state.name,
  age: state.age,
}));

// 使用 shallow 比较
import { shallow } from 'zustand/shallow';
const { name, age } = useStore(
  (state) => ({ name: state.name, age: state.age }),
  shallow
);
```

## 持久化

```ts
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export const useStore = create(
  persist(
    (set) => ({
      theme: 'light',
      setTheme: (theme: string) => set({ theme }),
    }),
    {
      name: 'app-storage',
    }
  )
);
```

## 最佳实践

1. 按业务模块拆分 store，避免单一 store 过大
2. 使用 TypeScript 定义完整类型
3. 异步操作直接写在 store 中，无需额外 middleware
4. 使用 selector 精确获取需要的状态，减少渲染
