// 静态 mock 数据：Chat 页面
// 字段命名对齐后端资源模型（session / session_workspace / source_workspace），
// 后续接入 gateway_service 时只需替换数据来源，无需改组件结构。

export const sessions = [
  {
    session_id: 's-1001',
    title: '电商后台重构',
    summary: 'Orchestrator 正在拆解结算模块任务',
    status: 'running',
    last_active_at: '2026-06-14T09:32:00Z',
  },
  {
    session_id: 's-1002',
    title: '官网落地页改版',
    summary: '已完成首屏组件，等待你确认配色',
    status: 'waiting',
    last_active_at: '2026-06-14T08:10:00Z',
  },
  {
    session_id: 's-1003',
    title: '订单服务接口梳理',
    summary: 'Backend Engineer 已产出接口草案',
    status: 'idle',
    last_active_at: '2026-06-13T19:45:00Z',
  },
  {
    session_id: 's-1004',
    title: '需求澄清：会员体系',
    summary: 'Product Manager 整理验收标准中',
    status: 'idle',
    last_active_at: '2026-06-13T14:20:00Z',
  },
];

// 以 session_id 为键的消息样例
export const messagesBySession = {
  's-1001': [
    { message_id: 'm-1', role: 'user', author: '你', content: '帮我把结算模块拆成可并行的子任务。' },
    {
      message_id: 'm-2',
      role: 'agent',
      author: 'Orchestrator',
      content: '已生成 Plan：1) 拆分价格计算 2) 优惠券校验 3) 支付回调。前两项可并行，我先派发给 Backend Engineer。',
    },
    { message_id: 'm-3', role: 'user', author: '你', content: '可以，优先保证支付回调的幂等性。' },
    {
      message_id: 'm-4',
      role: 'agent',
      author: 'Backend Engineer',
      content: '收到。我会在 sandbox 中实现幂等键方案，并先产出 Proposal 供你确认。',
    },
  ],
  's-1002': [
    { message_id: 'm-1', role: 'user', author: '你', content: '首屏 hero 区想要更轻量的风格。' },
    {
      message_id: 'm-2',
      role: 'agent',
      author: 'Frontend Engineer',
      content: '已调整为浅色渐变 + 单栏排版，组件已经在 session workspace 内更新，等待你确认配色。',
    },
  ],
  's-1003': [
    {
      message_id: 'm-1',
      role: 'agent',
      author: 'Backend Engineer',
      content: '订单服务接口草案已产出，包含创建、查询、取消三个端点。',
    },
  ],
  's-1004': [
    {
      message_id: 'm-1',
      role: 'agent',
      author: 'Product Manager',
      content: '会员体系需求已拆为等级、权益、积分三块，验收标准整理中。',
    },
  ],
};

// 运行态侧栏占位数据（以 session_id 为键）
export const runtimeBySession = {
  's-1001': {
    session_title: '电商后台重构',
    session_status: 'running',
    session_workspace: 'sw-electron-checkout',
    source_workspace: 'src-ecommerce',
    agent_status: 'running',
    task_status: '派发中 (2/3)',
    plan_steps: 3,
  },
  's-1002': {
    session_title: '官网落地页改版',
    session_status: 'waiting',
    session_workspace: 'sw-landing-redesign',
    source_workspace: 'src-website',
    agent_status: 'idle',
    task_status: '等待确认',
    plan_steps: 2,
  },
  's-1003': {
    session_title: '订单服务接口梳理',
    session_status: 'idle',
    session_workspace: 'sw-order-api',
    source_workspace: 'src-ecommerce',
    agent_status: 'idle',
    task_status: 'idle',
    plan_steps: 1,
  },
  's-1004': {
    session_title: '需求澄清：会员体系',
    session_status: 'idle',
    session_workspace: 'sw-membership-spec',
    source_workspace: 'src-website',
    agent_status: 'idle',
    task_status: 'idle',
    plan_steps: 0,
  },
};
