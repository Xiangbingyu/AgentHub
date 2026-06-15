# 前端 RTK Query 缓存 + Workspace 首屏扁平化

## 背景与目标

切换页面（Chat ↔ Workspace）或重进时，组件本地 `useState` 状态随卸载丢失，每次都从零拉取 → 白屏等待。
Workspace 页更重：`listSourceWorkspaces` 后**对每个 source 各调一次 `getWorkspacePage`**（N+1），数据一多首屏明显慢。

目标（用户拍板）：
1. 用 **RTK Query** 做 stale-while-revalidate：先用缓存的旧数据立即渲染，后台 refetch，拿到新数据再重渲染。
2. **同时修 Workspace 首屏 N+1**：先只拉 source 列表快速出框架，tree / session_workspaces 只为「选中的 source」按需拉。

非目标：source/session 的编辑删除 UI、文件内容预览、git clone —— 本轮不动。

## 方案

### 依赖
- 新增 `@reduxjs/toolkit` + `react-redux`（RTK Query 随 toolkit 内置，无额外包）。

### 新增文件
- `src/store/api.js` —— `createApi`：
  - `baseQuery: fetchBaseQuery({ baseUrl: '/api' })`
  - `tagTypes: ['Session', 'SourceWorkspace']`
  - 查询 endpoints（providesTags）：
    - `listSessions` → `/sessions`，provides `Session` LIST
    - `getSessionPage(sessionId)` → `/session-page/:id`
    - `listSourceWorkspaces` → `/source-workspaces`，provides `SourceWorkspace` LIST
    - `getWorkspacePage(sourceId)` → `/workspace-page/:id`
    - `getWorkspaceTree({sourceId, path})` → `/source-workspaces/:id/tree?path=`（供目录展开用 lazy）
  - 变更 mutations（invalidatesTags）：
    - `postSessionMessage({sessionId, content})` → POST `/sessions/:id/messages`
    - `createSessionFromSource({source_workspace_id, title})` → invalidates `Session` LIST
    - `createSourceWorkspace({name, root_path})` → invalidates `SourceWorkspace` LIST
- `src/store/index.js` —— `configureStore({ reducer: { [api.reducerPath]: api.reducer }, middleware: gDM => gDM().concat(api.middleware) })`

### 修改文件
- `src/main.jsx` —— 用 `<Provider store={store}>` 包裹 `<App/>`。
- `src/utils/api.js` —— 只保留 `sessionStreamUrl`（SSE 用 EventSource，不归 RTK 管）。读/写函数迁入 RTK，删除迁走的导出。
- `src/pages/Chat/Chat.jsx`：
  - `sessions` 改 `useListSessionsQuery()`（`data` 即缓存，切回页面立即有数据）。
  - `activeSessionId` 仍是本地状态；默认选第一条用 effect 兜底。
  - session 历史改 `useGetSessionPageQuery(activeSessionId, { skip: !activeSessionId })`，用 `useMemo` 从 `page.main_timeline` 派生历史消息。
  - **SSE 实时消息**：保留本地 `liveBuffer` 状态，最终 `messages = useMemo(() => 合并 dedupe([...history, ...liveBuffer]) 按 sequence_no 排序)`。切 session 时清空 liveBuffer。
  - 建 session 改 `useCreateSessionFromSourceMutation`；成功后 `setActiveSessionId(new)`，列表靠 tag 失效自动刷新。
  - 发消息改 `usePostSessionMessageMutation`。
- `src/pages/Workspace/Workspace.jsx`（**修 N+1**）：
  - `sources` 改 `useListSourceWorkspacesQuery()` → 首屏立即出 source 列表骨架。
  - `selectedSourceId` 本地状态，默认第一条。
  - 只对选中的 source 调 `useGetWorkspacePageQuery(selectedSourceId, { skip })`，把它的 `tree`/`session_workspaces` 合并进传给 `WorkspaceBrowser` 的那个 source 对象（其余 source 先空，选中再拉）。
  - 目录展开 `handleExpandDirectory` 改用 `useLazyGetWorkspaceTreeQuery` 触发，children 注入逻辑沿用。
  - `detailsById` 改为按选中 source 的 query 数据即时构造，去掉一次性遍历全部 source。
  - 建 source 改 `useCreateSourceWorkspaceMutation`；成功靠 tag 失效自动刷新列表。

### stale-while-revalidate 如何生效
RTK Query 把结果缓存进 store，组件卸载后默认保留 `keepUnusedDataFor: 60s`。再次挂载时 `data` 直接来自缓存（立即渲染），同时 `refetchOnMountOrArgChange` 触发后台 refetch，`isFetching` 期间旧数据不消失，拿到新数据后自动重渲染。Mutation 用 tag 失效驱动相关列表自动刷新，无需手动 refresh。

## 验证
1. `npm run lint` 绿（注意 RTK 的 hooks 命名、exhaustive-deps）。
2. `npm run build` 绿。
3. 手测：
   - Chat ↔ Workspace 来回切，第二次起**无白屏**，旧数据先显示、后台刷新。
   - 新建 session / source 后列表自动刷新并可进入。
   - Chat 内发消息，SSE 回流的 assistant 消息正常追加（与历史不重复）。
   - Workspace 首屏只发 1 次 source 列表请求，选中某 source 才拉它的 tree（Network 面板确认 N+1 消除）。

## 提交
全部实现 + 验证通过后**单次提交**（不分步提交）。
