export const mockWorkspaces = [
  {
    workspace_id: 'workspace-1',
    name: 'backend-runtime-workspace',
    root_path: 'E:/Github/AgentHub-weon/backend/.AgentHub/workspaces/workspace-1',
    status: 'ready',
    files: [
      {
        id: 'workspace-1:docs',
        type: 'directory',
        name: 'docs',
        path: 'docs',
        children: [
          {
            id: 'workspace-1:docs/superpowers',
            type: 'directory',
            name: 'superpowers',
            path: 'docs/superpowers',
            children: [
              {
                id: 'workspace-1:docs/superpowers/specs',
                type: 'directory',
                name: 'specs',
                path: 'docs/superpowers/specs',
                children: [
                  {
                    id: 'workspace-1:docs/superpowers/specs/2026-06-17-backend-leader-callback-hint-persistence-design.md',
                    type: 'file',
                    name: '2026-06-17-backend-leader-callback-hint-persistence-design.md',
                    path: 'docs/superpowers/specs/2026-06-17-backend-leader-callback-hint-persistence-design.md',
                  },
                ],
              },
            ],
          },
        ],
      },
      {
        id: 'workspace-1:plans',
        type: 'directory',
        name: 'plans',
        path: 'plans',
        children: [
          {
            id: 'workspace-1:plans/current-plan.json',
            type: 'file',
            name: 'current-plan.json',
            path: 'plans/current-plan.json',
          },
        ],
      },
      {
        id: 'workspace-1:app',
        type: 'directory',
        name: 'app',
        path: 'app',
        children: [
          {
            id: 'workspace-1:app/runtime',
            type: 'directory',
            name: 'runtime',
            path: 'app/runtime',
            children: [
              {
                id: 'workspace-1:app/runtime/agentscope',
                type: 'directory',
                name: 'agentscope',
                path: 'app/runtime/agentscope',
                children: [
                  {
                    id: 'workspace-1:app/runtime/agentscope/chat_runtime.py',
                    type: 'file',
                    name: 'chat_runtime.py',
                    path: 'app/runtime/agentscope/chat_runtime.py',
                  },
                ],
              },
            ],
          },
        ],
      },
    ],
  },
  {
    workspace_id: 'workspace-2',
    name: 'frontend2-mock-workspace',
    root_path: 'E:/Github/AgentHub-weon/frontend2',
    status: 'ready',
    files: [
      {
        id: 'workspace-2:src',
        type: 'directory',
        name: 'src',
        path: 'src',
        children: [
          {
            id: 'workspace-2:src/pages',
            type: 'directory',
            name: 'pages',
            path: 'src/pages',
            children: [
              {
                id: 'workspace-2:src/pages/Team',
                type: 'directory',
                name: 'Team',
                path: 'src/pages/Team',
                children: [
                  {
                    id: 'workspace-2:src/pages/Team/Team.jsx',
                    type: 'file',
                    name: 'Team.jsx',
                    path: 'src/pages/Team/Team.jsx',
                  },
                ],
              },
            ],
          },
        ],
      },
    ],
  },
];

export const mockWorkspaceDetails = {
  'workspace-1': {
    title: 'backend-runtime-workspace',
    type_label: 'Workspace',
    path: 'E:/Github/AgentHub-weon/backend/.AgentHub/workspaces/workspace-1',
    description: '状态：ready · 绑定到 session 创建时显式选择的独立产品资源',
    bindings: ['当前绑定 session：补完 AgentScope callback 主链', '当前绑定 team：Backend Team'],
    preview_kind: 'note',
    preview: '这是一个独立的产品级 Workspace。它不承载 Team/Agent 的能力配置，只承载文件树、文件内容和执行上下文。',
  },
  'workspace-1:plans/current-plan.json': {
    title: 'current-plan.json',
    type_label: 'Workspace File',
    path: 'plans/current-plan.json',
    description: 'utf-8 · 1.1 KB',
    bindings: ['runtime current_plan 快照来源文件'],
    preview_kind: 'code',
    preview:
      '{\n  "goal": "persist callback hint as assistant message",\n  "steps": [\n    {"status": "completed", "content": "drain leader inbox"},\n    {"status": "completed", "content": "persist assistant hint"}\n  ]\n}',
  },
  'workspace-1:app/runtime/agentscope/chat_runtime.py': {
    title: 'chat_runtime.py',
    type_label: 'Workspace File',
    path: 'app/runtime/agentscope/chat_runtime.py',
    description: 'utf-8 · 4.8 KB',
    bindings: ['callback 主链补完的核心实现文件'],
    preview_kind: 'code',
    preview:
      "async def run_wakeup(...):\n    await self._persist_wakeup_hints(...)\n    await chat_service.run(..., input_msg=None)",
  },
  'workspace-2': {
    title: 'frontend2-mock-workspace',
    type_label: 'Workspace',
    path: 'E:/Github/AgentHub-weon/frontend2',
    description: '状态：ready · 用于前端视觉复刻与后续接口接入',
    bindings: ['当前聚焦页面：Team / Session / Workspace mock shell'],
    preview_kind: 'note',
    preview: '这个 workspace 用来承载 frontend2 的 mock 页面实现。后续可以逐步接入真实后端接口。',
  },
  'workspace-2:src/pages/Team/Team.jsx': {
    title: 'Team.jsx',
    type_label: 'Workspace File',
    path: 'src/pages/Team/Team.jsx',
    description: 'utf-8 · 2.3 KB',
    bindings: ['Team 产品资源展示页'],
    preview_kind: 'code',
    preview: "export default function Team() {\n  return <div className=\"team-page\">...</div>;\n}",
  },
};
