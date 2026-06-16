# Frontend Chat 与 Workspace 页面框架设计

## 概述

当前仓库已经完成后端第一阶段重构：

- `agent_service` 负责 `session`、`source_workspace`、`session_workspace`、`domain_event` 等核心资源
- `gateway_service` 负责前端页面聚合接口与 `SSE` 实时流入口

当前前端仍然是 Vite + React 的初始脚手架，尚未形成正式页面框架。

本次设计的目标不是直接接入后端接口，而是先搭建两个核心页面的静态前端框架：

- `Chat`
- `Workspace`

视觉与布局上参考 `E:\Github\EchoMind\frontend` 的现有实现，并整体采用接近飞书 IM 的工作台风格。

## 目标

- 为 `frontend` 搭建正式的页面骨架，而不是继续停留在脚手架默认页。
- 只实现 `Chat` 和 `Workspace` 两个一级页面。
- 复刻 `EchoMind` 的整体布局组织方式，而不是任意新做一套 dashboard。
- 将页面结构与当前后端资源模型保持一致，尤其是：
  - `session`
  - `source_workspace`
  - `session_workspace`
- 当前阶段仅实现静态页面框架与分区，不接任何真实接口。
- 为下一阶段接入 `gateway_service` 聚合接口保留清晰边界。

## 非目标

- 不在本阶段接入任何 HTTP API。
- 不在本阶段接入 `SSE` 或 WebSocket。
- 不在本阶段实现真实消息发送、会话创建、workspace 创建、文件读取、代码编辑。
- 不在本阶段实现复杂状态管理方案，如全局 store、context-driven data layer 或缓存层。
- 不在本阶段实现完整移动端适配，只要求桌面端框架稳定，窄屏下不出现明显断裂。
- 不在本阶段复刻 EchoMind 的全部业务细节，只复刻页面骨架、布局语言和主要视觉组织方式。

## 参考基线

本设计明确参考 `EchoMind/frontend` 的实际源码，而不是抽象借用其页面名称。

参考的主要文件包括：

- `src/layouts/MainLayout.jsx`
- `src/components/Sidebar/Sidebar.jsx`
- `src/components/ConversationList/ConversationList.jsx`
- `src/components/WorkspacePanel/WorkspacePanel.jsx`
- `src/components/WorkspaceBrowser/WorkspaceBrowser.jsx`
- `src/pages/Messages/Messages.jsx`
- `src/pages/Workspace/Workspace.jsx`

参考结论如下：

- `EchoMind` 采用左侧全局导航 + 页面内部多栏布局的组织方式。
- 消息页并不是单纯二栏，而是“会话列表 + 主聊天区 + 运行态右栏”的复合布局。
- `Workspace` 页的核心不是“编辑器”，而是“资源导航区 + 状态/详情区”。
- 资源导航区内部通过可展开树状结构承载层级资源。

本设计保留这些结构语言，但将资源语义替换为当前仓库已经稳定下来的模型。

## 设计结论

### 总体结论

前端采用与 `EchoMind` 接近的三层结构：

- `MainLayout` 作为全局壳子
- `Chat` 与 `Workspace` 作为两个一级页面
- 页面内部再拆成若干职责单一的面板组件

页面路由仅保留两个入口：

- `/chat`
- `/workspace`

默认首页重定向到 `/chat`。

### 为什么当前阶段只做框架不接接口

原因有三点：

- 后端虽然已经具备 `agent_service` 与 `gateway_service` 的基础能力，但前端聚合响应字段还没有完全围绕最终页面打磨稳定。
- 当前用户目标非常明确，是先把页面骨架和布局框架复刻出来，而不是一边接接口一边返工 UI。
- 先将组件边界、页面分区与样式体系定稳，下一阶段接入 `gateway_service` 时改动会更小。

因此本阶段应当严格收敛为：

- 静态路由
- 静态 mock 数据
- 静态布局与样式
- 可见但不真正工作的交互外观

## 页面信息架构

### 1. 全局导航层

全局左侧导航栏固定存在于所有页面中。

职责：

- 在 `Chat` 与 `Workspace` 两个一级页面之间切换
- 提供统一应用入口与当前激活态反馈

约束：

- 采用“图标 + 文字”的纵向导航形式
- 不承载 session 列表
- 不承载 workspace 树
- 不承载复杂账号区、通知区或设置面板

这点与 `EchoMind` 的窄图标式 `Sidebar` 不完全相同。本项目会保留它的导航语义，但将宽度和排版调整为更适合当前阶段识别的“图标 + 文字”版本。

### 2. Chat 页面

`Chat` 页面采用三段式结构：

- 左：全局导航栏
- 中：统一 `session` 列表栏
- 右：聊天主区域

其中右侧聊天主区域内部再细分为：

- 主聊天面板
- 运行态侧栏

因此其视觉效果仍然接近 `EchoMind` 消息页“列表 + 聊天 + 右栏”的结构，只是当前阶段不会接入真实消息流。

关键约束：

- 中间栏仅展示一套统一 `session` 列表
- 明确不做“群聊 / 单聊”分区
- 不引入 `chat.type` 相关视觉分类
- 列表项、消息项、输入区、右侧运行态面板都只使用静态 mock 数据

### 3. Workspace 页面

`Workspace` 页面采用三段式结构：

- 左：全局导航栏
- 中：workspace 资源导航区
- 右：当前选中资源的详情/内容展示区

其核心参考对象是 `EchoMind` 的 `WorkspaceBrowser`，但资源层级不沿用其原始的 `workspace -> project -> file` 语义，而是替换为当前仓库的真实模型：

```text
source_workspace
  -> session_workspace
    -> folders/files (静态占位)
```

这意味着：

- 顶层是多个 `source_workspace`
- 展开后显示一个 `source_workspace` 下的多个 `session_workspace`
- 再向下可显示静态文件夹/文件占位节点，用于复刻资源树视觉结构

因此这个页面的本质不是“编辑器页”，而是“资源浏览器页”。

## 组件划分

### 1. `MainLayout`

职责：

- 提供全局应用壳子
- 固定渲染左侧导航栏
- 承载路由出口

它只处理全局框架，不承载页面级数据与业务判断。

### 2. `Sidebar`

职责：

- 展示全局一级导航
- 提供 `Chat` 与 `Workspace` 两个入口
- 展示当前激活页面状态

视觉要求：

- 图标 + 文字纵向排列
- 飞书风格的浅灰侧栏背景
- 当前激活项有明显高亮态

### 3. `SessionList`

职责：

- 作为 `Chat` 页中间栏
- 承载统一 `session` 列表
- 提供搜索框和新建按钮的视觉占位

与 `EchoMind` 的差异：

- 删除 `单聊 / 群聊` tabs
- 删除基于 `type` 的列表分组与标签
- 所有会话以同一种结构展示

保留的设计语言：

- 顶部标题区
- 搜索框
- 列表滚动区
- 当前项高亮
- 时间与摘要副信息

### 4. `ChatPanel`

职责：

- 作为 `Chat` 页右侧主体中的主聊天面板
- 展示顶部标题栏、消息流区域、底部输入区占位

当前阶段只实现：

- 用户消息和 agent 消息的静态样例
- 输入框和发送按钮的视觉结构
- 会话标题、状态标签等占位元素

当前阶段不实现：

- 发送逻辑
- 流式消息
- 输入状态同步

### 5. `RuntimePanel`

职责：

- 作为 `Chat` 页最右侧运行态侧栏
- 语义上对应 `EchoMind` 的 `WorkspacePanel`
- 展示当前会话绑定的运行态上下文占位

展示内容采用当前后端模型命名，而不是沿用旧的 project 语义，例如：

- 当前 `session`
- 当前 `session_workspace`
- 绑定的 `source_workspace`
- runtime / domain 状态占位

当前阶段只做静态信息卡片。

### 6. `WorkspaceBrowser`

职责：

- 作为 `Workspace` 页中间资源导航区
- 对应 `EchoMind` `WorkspaceBrowser` 的左侧导航语义
- 通过树状结构展示 `source_workspace -> session_workspace -> files` 的静态层级

应包含的结构：

- 页面标题区
- 资源说明/计数标签
- 可展开树节点
- source workspace 节点
- session workspace 节点
- 静态文件夹/文件节点

保留的设计语言：

- 展开/收起箭头
- 图标化资源节点
- 选中态高亮
- 缩进层级
- 轻量操作位占位

### 7. `WorkspaceDetailPanel`

职责：

- 作为 `Workspace` 页右侧详情展示区
- 对应 `EchoMind` `WorkspaceBrowser` 右侧状态/详情区语义

其本质不是完整编辑器，而是“选中资源的详情/预览面板”。

建议内容结构：

- 顶部标题栏：当前选中资源名、资源类型标签
- 信息卡片区：路径、描述、绑定关系、状态占位
- 底部内容预览区：静态代码块、README 占位或目录说明占位

这样既能保持“右侧代码展示区”的视觉感受，又不提前承诺完整编辑器能力。

## 页面拼装方式

### Chat 页面拼装

`pages/Chat/Chat.jsx` 负责将以下结构组合起来：

```text
Sidebar | SessionList | ChatPanel + RuntimePanel
```

布局原则：

- `SessionList` 采用固定或半固定宽度
- `ChatPanel` 为主自适应区
- `RuntimePanel` 为固定宽度右栏

### Workspace 页面拼装

`pages/Workspace/Workspace.jsx` 负责将以下结构组合起来：

```text
Sidebar | WorkspaceBrowser | WorkspaceDetailPanel
```

布局原则：

- `WorkspaceBrowser` 作为资源树导航区，采用固定或半固定宽度
- `WorkspaceDetailPanel` 作为主自适应区

## 目录结构

建议采用与 `EchoMind` 近似、但更贴当前阶段目标的目录结构：

```text
frontend/src/
  components/
    Sidebar/
      Sidebar.jsx
      Sidebar.css
    SessionList/
      SessionList.jsx
      SessionList.css
    ChatPanel/
      ChatPanel.jsx
      ChatPanel.css
    RuntimePanel/
      RuntimePanel.jsx
      RuntimePanel.css
    WorkspaceBrowser/
      WorkspaceBrowser.jsx
      WorkspaceBrowser.css
    WorkspaceDetailPanel/
      WorkspaceDetailPanel.jsx
      WorkspaceDetailPanel.css
  data/
    mockChat.js
    mockWorkspace.js
  layouts/
    MainLayout.jsx
    MainLayout.css
  pages/
    Chat/
      Chat.jsx
      Chat.css
    Workspace/
      Workspace.jsx
      Workspace.css
  App.jsx
  index.css
  main.jsx
```

## 数据组织策略

当前阶段不接任何接口，因此所有展示数据来自本地 mock 文件。

### `mockChat.js`

负责提供：

- session 列表数据
- 消息列表示例
- 运行态侧栏占位数据

### `mockWorkspace.js`

负责提供：

- source workspace 列表
- session workspace 层级
- 静态文件树
- 右侧详情区占位数据

这样做的目的，是让后续替换为 `gateway_service` 返回值时，只需要替换数据来源，而不是重写组件结构。

## 样式策略

### 1. 样式组织

延续 `EchoMind` 的组织方式：

- 每个组件单独配套一个 CSS 文件
- 全局变量与基础 reset 放在 `index.css`

当前阶段不引入 CSS-in-JS，也不引入额外样式框架。

### 2. 视觉基调

整体采用接近飞书 IM 的工作台风格：

- 左导航浅灰背景
- 列表区白底
- 主区浅灰底色
- 卡片与面板使用细边框、轻圆角、低对比阴影
- 激活态使用偏蓝色高亮

### 3. 响应式约束

本阶段优先桌面端。

要求：

- 在常见桌面宽度下布局稳定
- 窄屏下不出现重叠、溢出或结构断裂
- 不追求完整移动端交互

## 与后续后端接入的衔接方式

本设计虽然不直接接接口，但组件边界必须为后续接入保留自然映射：

- `SessionList` 未来对应 `gateway_service` 的 session 页面聚合数据
- `ChatPanel` 未来对应 session 主时间线和消息流
- `RuntimePanel` 未来对应 `session`、`session_workspace`、runtime/domain 状态
- `WorkspaceBrowser` 未来对应 `workspace_page` 聚合出的 `source_workspace` 与 `session_workspace` 树
- `WorkspaceDetailPanel` 未来对应当前选中资源的详情投影

这保证了本次静态框架不会成为一次性 demo，而是能直接演进为正式前端。

## 测试与验证策略

本阶段主要验证点不是业务逻辑，而是框架稳定性。

应验证：

- 页面路由是否正常切换
- 左侧导航激活态是否正确
- `Chat` 与 `Workspace` 的页面框架是否完整呈现
- 多栏布局在桌面宽度下是否稳定
- 静态 mock 数据是否能完整驱动页面占位展示

当前阶段不要求：

- 接口联调测试
- 实时流测试
- 复杂交互状态测试

## 实施边界

本设计严格限制为“前端页面框架搭建”。

允许实现：

- 路由
- 页面布局
- 组件拆分
- 静态 mock 数据
- 样式系统

不允许在本阶段偷偷扩展为：

- 真接口联调
- 真会话创建流程
- 真 workspace 管理流程
- 真文件树加载
- 真代码编辑器接入

这是为了确保这一轮工作聚焦在“先把壳子搭稳”。
