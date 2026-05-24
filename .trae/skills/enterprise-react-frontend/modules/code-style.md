# 代码规范

## 格式规范

- 缩进：2空格
- 引号：JS单引号，JSX双引号
- 分号：行尾添加
- 行尾逗号

## 变量声明

```js
// good
const items = getItems();
const goSportsTeam = true;
let dragonball;
```

## 函数规范

- 匿名函数使用箭头函数
- 箭头函数参数加括号
- 异步函数使用 async/await

```js
// good
const fetchData = async () => {
  const res = await request.get('/api/data');
  return res;
};

[1, 2, 3].map((x) => x * 2);
```

## 模块导入

```js
// good
import { useState, useEffect } from 'react';
import { Button, Table } from 'antd';
import isEmpty from 'lodash/isEmpty';
import $http from './http';
```
