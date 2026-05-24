# API请求

## axios 封装

```ts
// services/request.ts
import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios';
import { message } from 'antd';

const createRequest = () => {
  const instance: AxiosInstance = axios.create({
    baseURL: import.meta.env.VITE_API_BASE_URL,
    timeout: 10000,
  });

  instance.interceptors.request.use((config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  });

  instance.interceptors.response.use(
    (response: AxiosResponse) => response.data,
    (error) => {
      const status = error.response?.status;
      if (status === 401) {
        message.error('登录已过期，请重新登录');
        // 跳转登录
      } else {
        message.error(error.message || '请求失败');
      }
      return Promise.reject(error);
    }
  );

  return instance;
};

export const request = createRequest();
```

## 页面API封装

```ts
// features/user/services/api.ts
import { request } from '@/services/request';

export interface UserInfo {
  id: string;
  name: string;
}

export const getUserInfo = (params: { id: string }) => 
  request.get<UserInfo>('/api/user/info', { params });

export const updateUserInfo = (data: Partial<UserInfo>) => 
  request.post('/api/user/update', data);
```

## 使用示例

```tsx
import { getUserInfo, updateUserInfo } from './services/api';

const UserDetail = ({ userId }: { userId: string }) => {
  const [data, setData] = useState<UserInfo | null>(null);

  useEffect(() => {
    getUserInfo({ id: userId }).then(setData);
  }, [userId]);

  const handleUpdate = async () => {
    await updateUserInfo({ id: userId, name: 'new name' });
  };

  return <div>{data?.name}</div>;
};
```

## 环境变量

```ts
// .env.development
VITE_API_BASE_URL=/api
VITE_APP_TITLE=管理后台

// .env.production
VITE_API_BASE_URL=https://api.example.com
```
