# 记忆压缩与 Session 设计

## 1. 设计目标

这套设计用于解决赛题中的长会话、多 Agent 群聊、共享历史、任务长期推进等问题。

核心目标：

- 长对话不能无限堆在一个 session 里
- 历史不能直接丢失，必须可追溯
- 当前工作区要尽量保持短上下文
- 历史召回不能只靠全文搜索
- `session_summary` 要成为 recall 的主入口

## 2. 总体结构

```text
session history        -> 原始消息历史
-> compression         -> 中段压缩
-> continuation session -> 新分段 session

session lineage        -> 父子 session 链路
-> root_session        -> 根 session
-> child sessions      -> 各段 continuation session

session summary        -> 每段 session 的压缩摘要
-> summary text        -> 文本摘要
-> summary index       -> 检索入口
-> detail recall       -> 命中后细检索

memory                 -> 长期记忆
-> project memory      -> 项目规则 / 稳定约束
-> user memory         -> 用户偏好 / 长期习惯
-> task memory         -> 任务状态 / 执行结论
```

## 3. Session 分段设计

### 3.1 基本规则

- 一个长会话不会永远只用一个 session
- 每次发生压缩，就新建一个 continuation session
- 新 session 通过 `parent_session_id` 指向上一个 session
- 所有分段最终都能追溯到 `root_session`

### 3.2 链路示意

```text
root_session        -> 初始 session
  -> child_session_1 -> 第 1 次压缩后的续接 session
  -> child_session_2 -> 第 2 次压缩后的续接 session
  -> child_session_3 -> 第 3 次压缩后的续接 session
```

### 3.3 为什么采用分段 session

- 不原地覆盖旧历史
- 每段 session 都有自己的上下文边界
- 历史追溯更清楚
- 更适合把压缩摘要单独建索引
- 更适合后续做分段召回

## 4. Compression 机制

### 4.1 压缩范围

```text
head messages     -> 保留
middle messages   -> 压缩
tail messages     -> 保留
```

### 4.2 压缩规则

- 最顶部稳定内容保留
- 最新活跃消息保留
- 只压缩中段历史
- 中段生成结构化 `session_summary`
- 压缩完成后新建 continuation session

### 4.3 `session_summary` 至少包含

- 本段主题
- 关键任务
- 关键决策
- 已完成事项
- 未完成事项
- 重要文件 / Proposal / 分支
- 风险点 / 阻塞点
- 可检索关键词

## 5. Session Summary 作为 RAG 主入口

### 5.1 核心思路

我这里不希望历史召回直接从所有原始消息开始，而是先从 `session_summary` 开始。

也就是：

```text
query
-> session_summary 检索
-> 命中相关 session 分段
-> 分段内细节检索
-> 返回 query-focused summary
```

### 5.2 两段式检索

第一段：粗检索

- 先在 `session_summary` 层检索
- 找到最相关的 session 分段
- 先确定“应该回忆哪几段历史”

第二段：细检索

- 进入命中的 session 分段
- 在该分段内部检索原始消息、工具结果、任务记录、Diff 摘要
- 再生成面向当前问题的摘要

### 5.3 这样设计的重点

- 先用摘要筛分段
- 再在小范围内查细节
- 充分利用分段 session 的结构
- 让 compression 产出的 summary 真正参与 recall

## 6. `session_summary` 的索引方案

这里的关键不是“是否要做 RAG”，而是 `session_summary` 用什么索引方案。

可以有三种路线：

### 6.1 PageIndex 方案

思路：

- 把每个 `session_summary` 当成一个 page
- 每个 page 记录：
  - `session_id`
  - `parent_session_id`
  - `root_session_id`
  - `summary`
  - `keywords`
  - `entities`
  - `time_range`
  - `task_refs`

检索方式：

- 先按关键词 / 实体 / 时间 / root_session 范围过滤
- 再做向量或文本排序
- 命中 page 后进入该 session 细检索

适合：

- 结构化程度高
- 任务、项目、时间范围都重要
- 需要明显利用 session 分段关系

### 6.2 传统 RAG 方案

思路：

- 直接把 `session_summary` 当作普通文档块
- 建 embedding index
- query 直接做向量召回

检索方式：

- query embedding
- summary embedding 匹配
- 召回 topK summaries
- 再进入对应 session 取细节

适合：

- 第一版快速落地
- 实现成本低
- 先验证 recall 效果

### 6.3 VCP 浪潮 RAG 方案

思路：

- 不只做 summary 向量召回
- 还结合层级摘要、任务上下文、阶段性摘要和当前 query 的意图
- 更像“按任务波次”做召回

检索方式可以设计成：

- 先判断 query 属于哪个任务波次 / 哪个 root_session / 哪个主题段
- 再在该波次内做 `session_summary` 检索
- 再回到具体 session 内做细检索

适合：

- 多 Agent 群聊
- 多轮规划和执行
- 同一个项目下长期有多个 topic 并行推进

## 7. Tag 层设计

我这里希望每个分段 session 不只产出 `session_summary`，还要同时产出一组高概括性的 `session_tags`。

结构变成：

```text
session
-> raw messages
-> session_summary
-> session_tags
```

### 7.1 `session_tags` 的作用

- 用来描述这一段 session 主要在做什么
- 用来表达主题、任务、状态和角色
- 用来给 recall 提供第一层粗筛入口

### 7.2 tag 的内容类型

每个 session 的 tag 可以分成几类：

- 主题类：`登录模块`、`首页重构`、`部署链路`
- 任务类：`前端开发`、`接口联调`、`测试修复`
- 状态类：`待确认`、`已阻塞`、`已完成`
- 角色类：`CodeAgent`、`DocAgent`、`TestAgent`
- 产物类：`Proposal`、`Diff`、`预览链接`

### 7.3 recall 结构升级

原来的 recall 更接近：

```text
query
-> session_summary 检索
-> 命中 session
-> session 内细检索
```

加入 tag 层后，升级成：

```text
query
-> session_tags / wave index
-> 命中相关 session 分段
-> session_summary 排序
-> session 内细检索
-> query-focused summary
```

### 7.4 tag 层的意义

- 先用 tag 做主题粗筛
- 再用 summary 做相关性排序
- 最后进入原始 session 做细节追溯

这样更适合：

- 分段 session
- 多 Agent 群聊
- 长时间任务推进
- 同一个项目下多个 topic 并行

### 7.5 与浪潮算法的结合

我这里更倾向于把 tag 层和浪潮算法结合起来。

也就是说：

- 每个 session 压缩时生成 `session_summary`
- 同时提取一组高概括性的 `session_tags`
- 再把这些 tag 组织成 wave index 或主题波次索引

这样 recall 时不只是查文本相似度，而是先判断：

- 当前 query 属于哪一类主题
- 当前 query 更接近哪一个任务波次
- 应该先召回哪几个 session 分段

## 8. 记忆层设计

这套方案里，记忆和 session history 仍然要分开。

### 8.1 Session History

- 保存原始消息
- 保存工具结果
- 保存 Diff / Proposal / 状态消息
- 用于细节追溯

### 8.2 Session Summary

- 保存每段 session 的压缩摘要
- 用于第一层 recall
- 作为 session RAG 主入口

### 8.3 Long-term Memory

- 保存项目长期规则
- 保存用户稳定偏好
- 保存关键任务结论
- 保存稳定事实，不保存全部聊天

## 9. 对赛题方案的意义

这套设计应用到赛题里，最终会形成：

```text
长群聊 / 长任务
-> 按压缩点切成多段 session
-> 每段 session 生成 summary
-> summary 建索引
-> query 先查 summary
-> 再回到具体 session 查细节
-> 当前 run 只拿相关分段上下文
```

这样可以同时满足：

- 长对话可持续
- 历史可追溯
- 当前上下文可控
- recall 成本可控
- 更适合多 Agent 群聊和长期任务推进
