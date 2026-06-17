export const mockSessions = [
  {
    session_id: 'session-1',
    title: '补完 AgentScope callback 主链',
    status: 'running',
    updated_at: '10:24',
    summary: 'Leader 正在汇总 worker callback，并同步右侧 runtime 面板。',
  },
  {
    session_id: 'session-2',
    title: '梳理 Team / Workspace 边界',
    status: 'idle',
    updated_at: '昨天',
    summary: '设计文档已经明确 Product Team 与 Runtime Team 的分层。',
  },
  {
    session_id: 'session-3',
    title: '验证 waiting_items 聚合',
    status: 'waiting',
    updated_at: '周一',
    summary: '等待用户确认 Write 工具调用。',
  },
];

export const mockMessages = [
  {
    message_id: 'm-1',
    kind: 'message',
    role: 'user',
    author: '你',
    content: '继续把 worker callback 主链补完，不要只停在 wakeup。',
  },
  {
    message_id: 'm-2',
    kind: 'tool_call',
    tool_name: 'TeamSay',
    arguments: { agent: 'worker-a', content: 'worker finished task' },
  },
  {
    message_id: 'm-3',
    kind: 'message',
    role: 'agent',
    author: 'Leader Agent',
    content:
      '我已经消费了 worker callback，并将 hint 作为权威 assistant message 持久化，避免只停留在运行时内存态。',
  },
  {
    message_id: 'm-4',
    kind: 'plan',
    title: '前端复刻计划',
    status: 'in_progress',
    goal: '在 frontend2 中复刻 session 页面与 workspace 页面视觉结构。',
    steps: [
      { step_id: 'p-1', content: '搭建路由与主布局', status: 'completed' },
      { step_id: 'p-2', content: '实现 Chat 页 mock 组件', status: 'in_progress' },
      { step_id: 'p-3', content: '实现 Workspace 页 mock 组件', status: 'pending' },
    ],
    file_path: 'docs/superpowers/specs/2026-06-17-frontend2-mock-page-replica-design.md',
  },
];

export const mockRuntime = {
  session_title: '补完 AgentScope callback 主链',
  session_status: 'running',
  session_team: 'Backend Team',
  session_workspace: 'backend-runtime-workspace',
  agent_status: 'running',
  task_status: 'processing callback hint persistence',
  plan_steps: 3,
  current_summary: 'callback 已进入 leader persisted messages，stream 继续作为观察通道。',
  waiting_items: [
    {
      waiting_id: 'wait-1',
      title: 'Confirm Write',
      message: 'Write tool requires confirmation before applying the patch.',
      status: 'pending',
    },
  ],
  agent_statuses: [
    { agent_id: 'leader-agent', role: 'leader', status: 'running' },
    { agent_id: 'worker-a', role: 'worker', status: 'idle' },
  ],
};
