# 记忆压缩与 Session 设计-MVP

## 1. MVP 目标

这版只解决一个最核心的问题：

- 长群聊和长任务不能把全部历史一直塞进当前上下文

因此，MVP 只保留三层：

- `compression`
- `mem0`
- `memory.md`

不做：

- 精确历史回溯
- 分段 session 的复杂 recall
- `session_summary` RAG
- PageIndex
- 浪潮 RAG

## 2. MVP 总体结构

```text
当前会话
-> 原始消息持续追加
-> 超长后做中段压缩
-> 当前上下文只保留 head + summary + tail

长期记忆
-> mem0
-> memory.md
```

## 3. 上下文策略

### 3.1 当前 session

当前 session 仍然保存完整原始消息。

但模型实际看到的上下文不是全部原始消息，而是：

```text
head messages   -> 顶部稳定信息
summary         -> 中段压缩摘要
tail messages   -> 最新活跃消息
```

### 3.2 压缩触发后

- 不需要新建分段 session
- 不需要复杂 lineage
- 只需要把当前 session 的中段历史压成一段 summary
- 后续继续在当前 session 上推进

这版的重点是：

- 先把上下文长度控住
- 先让长对话能持续跑

## 4. Compression 设计

### 4.1 压缩范围

```text
head messages     -> 保留
middle messages   -> 压缩
tail messages     -> 保留
```

### 4.2 压缩结果

压缩后当前上下文变成：

```text
system / stable context
-> head messages
-> compression summary
-> tail messages
```

### 4.3 summary 至少包含

- 当前主题
- 已完成事项
- 未完成事项
- 当前任务状态
- 当前阻塞点
- 重要决策
- 重要文件 / Proposal / 分支

## 5. 长期记忆策略

这版不做复杂长期历史检索，长期历史直接交给 `mem0`。

### 5.1 mem0

`mem0` 负责：

- 用户长期偏好
- 项目长期规则
- 反复出现的重要事实
- 跨 session 的长期记忆

### 5.2 memory.md

再保留一个轻量的 `memory.md`：

- 保存模型判断为“关键但需要稳定可见”的记忆
- 更像项目运行中的核心记忆板

### 5.3 memory tool

模型可以通过 `memory tool` 主动把某些内容写入 `memory.md`。

写入原则：

- 不是所有聊天都写
- 只记录关键记忆
- 优先记录稳定约束和高价值事实

例如：

- 项目技术栈
- 固定命令
- 重要目录约定
- 用户明确要求的输出风格
- 当前项目的长期规则

## 6. MVP 的实际策略

这版最终采用：

```text
短期上下文
-> compression

跨 session 长期记忆
-> mem0

关键稳定记忆
-> memory.md
```

也就是：

- 近处靠压缩
- 远处靠 mem0
- 关键规则靠 memory.md

## 7. 为什么这样适合 MVP

- 实现简单
- 不依赖复杂 session 切分
- 不依赖复杂 recall pipeline
- 先解决上下文爆炸问题
- 先保留一个最小可用的长期记忆机制

## 8. 后续再升级的方向

如果后面时间够，再往完整版演进：

- 分段 session
- `session_summary` 检索
- tag 层
- PageIndex
- 浪潮 RAG

但 MVP 阶段不需要先做这些。
