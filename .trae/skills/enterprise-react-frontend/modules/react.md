# React/TSX规范

## 组件规范

优先使用函数组件 + Hooks

```tsx
import { useState, useEffect, useMemo, useCallback } from 'react';
import './index.scss';

interface Props {
  title: string;
  options?: Record<string, unknown>;
}

const MyComponent = ({ title, options = {} }: Props) => {
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchData();
    return () => {
      // cleanup
    };
  }, []);

  const value = useMemo(() => {
    return computeValue();
  }, [dependencies]);

  const handleClick = useCallback(() => {
    // ...
  }, [dependencies]);

  return <div>{title}</div>;
};

export default MyComponent;
```

## React 18 新特性

### Suspense + 懒加载

```tsx
import { lazy, Suspense } from 'react';

const LazyComponent = lazy(() => import('./LazyComponent'));

const App = () => (
  <Suspense fallback={<Spin />}>
    <LazyComponent />
  </Suspense>
);
```

### useTransition

```tsx
import { useTransition, useState } from 'react';

const [isPending, startTransition] = useTransition();
const [filter, setFilter] = useState('');

const handleChange = (value: string) => {
  startTransition(() => {
    setFilter(value);
  });
};
```

### useDeferredValue

```tsx
import { useDeferredValue } from 'react';

const deferredValue = useDeferredValue(value);
```

## 自定义Hooks

使用 useXxx 命名

```ts
// hooks/useWatermark.ts
const useWatermark = (text: string) => {
  // implementation
  return { setWatermark, removeWatermark };
};
export default useWatermark;
```

## Props 规范

```tsx
// good
<Foo
  userName="hello"
  hidden
/>

{items.map((item) => (
  <Item key={item.id} {...item} />
))}
```

## JSX 格式

```tsx
// good
<Foo
  longParam="bar"
  anotherParam="baz"
/>

{showButton && <Button />}

{condition ? <A /> : <B />}
```

## 严格模式

开发环境使用 StrictMode 检查副作用

```tsx
import { StrictMode } from 'react';

<StrictMode>
  <App />
</StrictMode>
```
