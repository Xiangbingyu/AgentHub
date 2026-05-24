# 通用组件封装

项目在 `components/` 目录下封装了大量通用组件，避免重复造轮子。

## 表单组件

| 组件 | 说明 |
|------|------|
| `Form` | 通用表单组件，支持配置化生成表单 |
| `SearchForm` | 搜索表单组件 |

```tsx
import Form from 'components/form';
import SearchForm from 'components/searchForm';

const formList = [
  { label: '名称', key: 'name', type: 'input' },
  { label: '类型', key: 'type', type: 'select', options: [...] },
];
<Form formList={formList} onSubmit={handleSubmit} />
```

## 表格组件

| 组件 | 说明 |
|------|------|
| `Table` | 通用表格组件，支持列配置、分页、排序等 |
| `EditableTable` | 可编辑表格 |

```tsx
import Table from 'components/table';

<Table
  columns={columns}
  dataSource={data}
  rowKey="id"
  pagination={false}
/>
```

## 弹窗组件

| 组件 | 说明 |
|------|------|
| `Modal` | 通用弹窗组件 |
| `Drawer` | 抽屉组件 |

## 按钮组件

| 组件 | 说明 |
|------|------|
| `DebounceButton` | 防抖按钮，防止重复点击 |

```tsx
import DebounceButton from 'components/debounceButton';

<DebounceButton type="primary" onClick={handleSubmit}>
  提交
</DebounceButton>
```

## 其他常用组件

| 组件 | 说明 |
|------|------|
| `Breadcrumb` | 面包屑组件 |
| `Pagination` | 分页组件 |
| `Ellipsis` | 文字省略+tooltip |
| `ErrorBoundary` | 错误边界 |

## 自定义Hooks

项目在 `hooks/` 目录下封装了常用 Hooks：

| Hook | 说明 |
|------|------|
| `useWatermark` | 水印功能 |
| `useNetwork` | 网络状态监控 |
| `useCopy` | 复制功能 |
| `useAutoHeight` | 自动高度 |
| `useInterval` | 定时器 |
| `useDebounce` | 防抖 |
| `useThrottle` | 节流 |

```tsx
import useWatermark from 'hooks/useWatermark';
import useAutoHeight from 'hooks/useAutoHeight';

const MyComponent = () => {
  useWatermark();
  const height = useAutoHeight();
  return <div style={{ height }}>...</div>;
};
```
