# 动态加载使用示例

## 基本用法

```javascript
const loader = require('./loader');

// 根据任务加载相关模块
const content = loader.dynamicLoad('开发新功能');
console.log(content);
```

## 任务类型与模块映射

| 关键词 | 加载模块 |
|--------|----------|
| 开发/新增/功能 | guide, naming, code-style, react, components, api, commands |
| 重构 | refactor, guide, code-style |
| 修复/bug/fix | guide, code-style, react, quality |
| 了解/结构 | tech-stack, directory, naming |
| redux/状态 | redux |
| 组件/component | react, components, css, naming |
| api/接口 | api, commands |
| review/审查 | code-style, react, quality, convention |

## 模块列表

| 模块名 | 内容 |
|--------|------|
| guide | 开发指南 |
| refactor | 重构指南 |
| tech-stack | 技术栈 |
| directory | 目录结构 |
| naming | 文件命名规范 |
| code-style | 代码规范 |
| react | React/JSX规范 |
| css | CSS规范 |
| components | 通用组件封装 |
| redux | 状态管理 |
| api | API请求 |
| commands | 命令参考 |
| convention | 项目约定 |
| quality | 质量检查 |
