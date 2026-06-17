export const mockTeams = [
  {
    team_id: 'team-1',
    name: 'Backend Team',
    description: '负责 AgentScope runtime mainline 与 session/team/workspace 后端聚合。',
    leader_agent_id: 'leader-agent',
    member_agent_ids: ['worker-a', 'worker-b'],
    is_default: true,
    default_model_config: {
      provider: 'dashscope',
      model: 'qwen-max',
      temperature: 0,
    },
    tools: ['bash', 'write', 'grep', 'read'],
    mcps: ['filesystem', 'workspace-browser'],
    skills: ['systematic-debugging', 'test-driven-development'],
  },
  {
    team_id: 'team-2',
    name: 'Runtime Team',
    description: '关注 callback、waiting、cancel、session_stream 这些 runtime 收口问题。',
    leader_agent_id: 'runtime-leader',
    member_agent_ids: ['worker-runtime-a'],
    is_default: false,
    default_model_config: {
      provider: 'dashscope',
      model: 'qwen-plus',
      temperature: 0,
    },
    tools: ['bash', 'read'],
    mcps: ['filesystem'],
    skills: ['verification-before-completion'],
  },
];
