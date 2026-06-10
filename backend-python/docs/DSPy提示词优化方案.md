# DSPy 提示词优化方案

## 1. 目标

这份文档只解决一个问题：

- 如何在 AgentHub 中引入一个基于 DSPy 的离线提示词优化器，用来提升 orchestrator 回复的稳定性与决策质量。

优化目标：

- 提高 orchestrator 的任务决策稳定性（先问、先计划、先委派、直接回答）
- 提高稳定层 prompt 的格式一致性
- 提高系统指令遵循度
- 优化完整执行轨迹中的策略选择，而不只是单步回复

## 2. 总原则

- DSPy 负责离线优化，不负责线上控制流
- runtime 继续负责 prompt 拼装、tool 注入、loop 状态机和 tool dispatch
- 优化单元是完整的 orchestrator 执行轨迹，而不是单步输入输出
- 优化器同时产出稳定层 section 文本和策略建议，两者在同一个 program 中联合优化
- 优化结果必须可版本化、可回滚、可按 section 回填 runtime
- environment、tool schema、input event context 不参与优化
- loop 状态机始终由 runtime 代码执行，DSPy 只产出策略建议

## 3. 放置位置

```text
app/prompt_optimization/
├─ datasets/
│  ├─ orchestrator_train.jsonl
│  ├─ orchestrator_dev.jsonl
│  └─ orchestrator_holdout.jsonl
├─ evaluators/
│  ├─ hard_metrics.py
│  ├─ behavior_metrics.py
│  └─ stability_metrics.py
├─ programs/
│  ├─ orchestrator_signature.py
│  ├─ orchestrator_program.py
│  └─ section_renderers.py
├─ optimizers/
│  └─ compile_orchestrator.py
├─ artifacts/
│  └─ orchestrator/
│     └─ optimized_v1/
│        ├─ artifact.json
│        └─ sections/
├─ reports/
│  └─ eval_*.json
└─ README.md
```

各目录职责：

- `datasets/`：完整轨迹样本，按 `train / dev / holdout` 三集合管理
- `evaluators/`：硬指标、行为指标、稳定性指标评分函数
- `programs/`：DSPy Signature、统一优化 program、section 渲染器
- `optimizers/`：优化入口脚本，调用 `MIPROv2` 编译
- `artifacts/`：编译产物，按版本存储，可直接回填 runtime section
- `reports/`：每次编译和评测结果，用于回归比较

## 4. 优化对象

### 参与优化的 section

- instruction section：orchestrator 核心行为规范
- orchestrator_mode section：当前模式下的策略描述
- user_prompt_policy：少量可配置的用户侧指令

### 不参与优化的部分

- environment section：运行时事实注入，不适合 DSPy 优化
- tool schema 注入：由 runtime 动态生成
- input event context：动态上下文，不属于稳定层
- loop 控制逻辑：始终由 runtime 状态机执行

### 优化方式

优化器以稳定层 section 的联合视图作为输入，同时产出：

1. instruction_block：回填 instruction section
2. orchestrator_mode_block：回填 orchestrator_mode section
3. next_action_policy：策略建议，供 runtime 参考（`plan / ask / delegate / read / update_plan / finish / dialogue`）

不采用“整段拼接再事后猜着拆”的方式，而是整体看、分块出：优化器看到完整上下文，但输出必须保持 section 级可解释、可回填、可回滚。

## 5. 训练集设计

### 核心原则

训练集的基本单元是完整的 orchestrator 执行轨迹，而不是单步输入输出。每条样本描述一次完整任务从开始到结束的行为序列，包括中间穿插的文件读取、计划修改等操作。

### 样本 Schema

```json
{
  "case_id": "orch_042",
  "trajectory_type": "ask_plan_delegate_read_update_finish",
  "trajectory": [
    {
      "step": 1,
      "event_type": "user_input",
      "content": "帮我重构这个模块",
      "expected_action": "ask_clarifying_question",
      "expected_tool": "question_tool"
    },
    {
      "step": 2,
      "event_type": "user_reply",
      "content": "只重构接口层，不动业务逻辑",
      "expected_action": "create_plan",
      "expected_tool": "plan_tool"
    },
    {
      "step": 3,
      "event_type": "plan_created",
      "expected_action": "delegate",
      "expected_tool": "delegate_tool"
    },
    {
      "step": 4,
      "event_type": "subtask_callback",
      "content": "子模型完成，但发现接口有歧义",
      "expected_action": "read_file",
      "expected_tool": "file_read_tool"
    },
    {
      "step": 5,
      "event_type": "file_read_done",
      "expected_action": "update_plan",
      "expected_tool": "plan_update_tool"
    },
    {
      "step": 6,
      "event_type": "plan_updated",
      "expected_action": "finish",
      "expected_tool": null
    }
  ],
  "hard_constraints": {
    "must_ask_before_plan": true,
    "must_not_skip_plan": true,
    "file_read_allowed_mid_flow": true
  }
}
```

### 必须覆盖的轨迹类型

| 类型 | 轨迹 |
|------|------|
| direct_answer | user_input -> finish |
| direct_dialogue | user_input -> dialogue（不使用工具） |
| plan_delegate_finish | user_input -> plan -> delegate -> finish |
| ask_plan_delegate_finish | user_input -> ask -> plan -> delegate -> finish |
| plan_delegate_update_finish | user_input -> plan -> delegate -> update_plan -> finish |
| ask_plan_delegate_read_update_finish | user_input -> ask -> plan -> delegate -> read_file -> update_plan -> finish |
| read_mid_flow | 任意流程中穿插一次或多次 `read_file` |

每种类型建议至少 15 到 20 条样本，覆盖不同任务领域和输入风格。

### 数据集划分

- train：用于 DSPy 编译优化，约 60%
- dev：用于编译过程中的评测，约 20%
- holdout：最终验收，不参与任何优化过程，约 20%

holdout 集的分数是上线的唯一判定标准。

## 6. DSPy Program 设计

### Signature

```python
class OrchestratorSignature(dspy.Signature):
    """
    Given the current runtime state, conversation history, and available tools,
    produce the orchestrator instruction block, mode block, and next action policy.
    """

    runtime_summary: str = dspy.InputField()
    conversation_history: str = dspy.InputField()
    available_tools: list[str] = dspy.InputField()
    current_step_event: str = dspy.InputField()

    instruction_block: str = dspy.OutputField()
    orchestrator_mode_block: str = dspy.OutputField()
    next_action_policy: str = dspy.OutputField()
```

`next_action_policy` 的合法值：

- `plan`
- `ask`
- `delegate`
- `read_file`
- `update_plan`
- `finish`
- `dialogue`

### Program

```python
class OrchestratorProgram(dspy.Module):
    def __init__(self):
        self.generate = dspy.ChainOfThought(OrchestratorSignature)

    def forward(
        self,
        runtime_summary,
        conversation_history,
        available_tools,
        current_step_event,
    ):
        return self.generate(
            runtime_summary=runtime_summary,
            conversation_history=conversation_history,
            available_tools=available_tools,
            current_step_event=current_step_event,
        )
```

### 优化器选择

- 首选 `MIPROv2`：适合 instruction-level prompt 搜索
- 备选 `COPRO`：更轻量，适合快速验证
- 第一阶段不使用多程序联合优化

## 7. Metric 设计

Metric 在轨迹级别评分，不在单步级别评分。

### 总分公式

```text
total_score =
  0.50 * behavior_score
+ 0.30 * format_score
+ 0.20 * stability_score
```

### 行为分（behavior_score）

评估每步 action 是否符合 `expected_action`，以及整条轨迹的策略顺序是否合理：

- 是否在信息不足时先提问
- 是否在有计划需求时先建计划
- 是否在计划建立后才委派
- 是否在需要时穿插 `read_file`
- 是否在任务完成后正确结束
- 是否在不需要工具时走普通对话流程

### 格式分（format_score）

评估 section 文本是否满足硬约束：

- `instruction_block` 是否包含必须字段
- `orchestrator_mode_block` 是否符合格式规范
- 是否出现禁止内容
- `next_action_policy` 是否为合法值

### 稳定性分（stability_score）

- 同一 case 多次采样时，`next_action_policy` 是否一致
- 语义改写输入后，核心决策是否稳定
- section 文本的关键结构在小扰动下是否保持稳定

稳定性分是区分“真正优化”和“过拟合到样本文风”的关键指标，不可省略。

## 8. Artifact 设计

优化产物以 section 级版本包的形式落盘，runtime 按 `artifact_id` 或配置开关选择加载。

### `artifact.json` 结构

```json
{
  "artifact_id": "orchestrator_optimized_v1",
  "target": "orchestrator_stable_sections",
  "version": "2026-05-28.1",
  "source_optimizer": "dspy_miprov2",
  "metrics": {
    "dev_total_score": 0.82,
    "holdout_total_score": 0.79,
    "behavior_score": 0.85,
    "format_score": 0.88,
    "stability_score": 0.86
  },
  "sections": {
    "instruction": "sections/instruction.txt",
    "orchestrator_mode": "sections/orchestrator_mode.txt",
    "user_prompt_policy": "sections/user_prompt_policy.txt"
  }
}
```

### 回写规则

- runtime 读取 `artifact_id` 对应的 section 文本，替换对应 section builder 的默认输出
- environment、tool schema、input event context 不受 artifact 影响
- 每次上线前必须在 holdout 集上验收，分数不低于当前线上版本才允许替换
- 旧版本 artifact 保留，支持一键回滚

## 9. 基本流程

```text
构建轨迹样本集（train / dev / holdout）
  ↓
定义 OrchestratorSignature 和 OrchestratorProgram
  ↓
定义三层 metric（行为 / 格式 / 稳定性）
  ↓
用 MIPROv2 在 train 集上编译
  ↓
在 dev 集上评测，调整编译参数
  ↓
在 holdout 集上最终验收
  ↓
产出 artifact（section 级版本包）
  ↓
回写到 runtime section builder
  ↓
A/B 对比线上效果
```

## 10. 防过拟合策略

- holdout 集严格隔离，不参与任何优化过程
- 训练集中加入语义改写样本（同一任务，不同表达方式）
- 覆盖所有 `trajectory_type`，避免只优化高频流程
- 稳定性分强制纳入总分，防止优化器只追求单次高分
- 每次编译后对比 dev 和 holdout 分数差距，差距超过 0.05 视为过拟合信号

## 11. 非目标

以下内容不在本方案范围内：

- 在线实时提示词重写
- 多 Agent 同时联合优化
- 自动修改 loop 状态机或 tool dispatch 逻辑
- 直接替换现有整条 prompt composer 结构
- 优化 environment、tool schema、input event context

## 12. 一句话总结

DSPy 在 AgentHub 中作为 `app/prompt_optimization/` 下的离线轨迹级优化器，以完整 orchestrator 执行轨迹为训练单元，用统一的 `OrchestratorProgram` 同时优化稳定层 section 文本和策略选择；输出保持 section 级可回填、可版本化、可回滚；loop 状态机始终由 runtime 执行，DSPy 只产出策略建议。
