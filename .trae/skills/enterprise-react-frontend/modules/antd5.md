# Ant Design 5.x 使用规范

## 简介

Ant Design 5.x 带来了 CSS-in-JS 方案，完全重写了组件，支持 Design Token 定制。

## 快速开始

```tsx
import { Button, ConfigProvider } from 'antd';

const App = () => (
  <ConfigProvider
    theme={{
      token: {
        colorPrimary: '#1677ff',
        borderRadius: 6,
      },
    }}
  >
    <Button type="primary">Primary</Button>
  </ConfigProvider>
);
```

## Design Token

### 全局Token

```tsx
<ConfigProvider
  theme={{
    token: {
      colorPrimary: '#1677ff',
      borderRadius: 6,
      fontSize: 14,
      colorBgContainer: '#ffffff',
    },
  }}
>
```

### 组件Token

```tsx
<ConfigProvider
  theme={{
    components: {
      Button: {
        primaryShadow: '0 2px 4px rgba(0,0,0,0.1)',
      },
      Table: {
        headerBg: '#f6f7f8',
      },
    },
  }}
>
```

## 主题切换

### 亮色/暗色主题

```tsx
import { theme } from 'antd';

<ConfigProvider
  theme={{
    algorithm: theme.darkAlgorithm, // 暗色主题
    // algorithm: theme.defaultAlgorithm, // 亮色主题
  }}
>
```

### 动态切换主题

```tsx
import { useState } from 'react';
import { ConfigProvider, theme } from 'antd';

const App = () => {
  const [darkMode, setDarkMode] = useState(false);
  
  return (
    <ConfigProvider
      theme={{
        algorithm: darkMode ? theme.darkAlgorithm : theme.defaultAlgorithm,
      }}
    >
      <button onClick={() => setDarkMode(!darkMode)}>切换主题</button>
    </ConfigProvider>
  );
};
```

## 组件使用变化

### 5.x 变化

```tsx
// 5.x 废弃了一些 API
// visible -> open (Modal, Drawer, Dropdown 等)
// onVisibleChange -> onOpenChange

// Modal
<Modal open={visible} onOpenChange={setVisible} />

// Drawer
<Drawer open={open} onOpenChange={setOpen} />
```

### Table 排序/筛选

```tsx
<Table
  columns={[
    {
      title: 'Name',
      dataIndex: 'name',
      sorter: (a, b) => a.name.localeCompare(b.name),
      filters: [...],
      onFilter: (value, record) => record.status === value,
    },
  ]}
/>
```

### Form

```tsx
import { Form } from 'antd';

const Demo = () => {
  const [form] = Form.useForm();
  
  const onFinish = (values: unknown) => {
    console.log(values);
  };
  
  return (
    <Form form={form} onFinish={onFinish}>
      <Form.Item name="username" rules={[{ required: true }]}>
        <Input />
      </Form.Item>
    </Form>
  );
};
```

## CSS-in-JS 样式覆盖

```tsx
import { useToken } from 'antd';

const { token } = useToken();

// 使用 token 中的值
<div style={{ background: token.colorBgContainer }}>
  Content
</div>
```

## 最佳实践

1. 使用 ConfigProvider 统一配置主题
2. 优先使用 Design Token，保持一致性
3. 组件废弃 API 需要同步更新 (visible -> open)
4. 暗色主题使用 darkAlgorithm
