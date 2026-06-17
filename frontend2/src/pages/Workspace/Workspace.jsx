import { useCallback, useMemo, useState } from 'react';
import { useAsyncResource } from '../../hooks/useAsyncResource';
import { api } from '../../utils/api';
import WorkspaceBrowser from '../../components/WorkspaceBrowser/WorkspaceBrowser';
import WorkspaceDetailPanel from '../../components/WorkspaceDetailPanel/WorkspaceDetailPanel';
import './Workspace.css';

function buildTreeNodes(workspaceId, entries, treeMap, expandedMap) {
  return (entries ?? []).map((entry) => {
    const nodeId = `${workspaceId}:${entry.path}`;
    const children = expandedMap[nodeId]
      ? buildTreeNodes(workspaceId, treeMap[nodeId] ?? [], treeMap, expandedMap)
      : entry.type === 'directory'
        ? null
        : undefined;

    return {
      id: nodeId,
      type: entry.type,
      name: entry.name,
      path: entry.path,
      children,
    };
  });
}

export default function Workspace() {
  const loadWorkspaces = useCallback(() => api.listWorkspaces(), []);
  const {
    data: workspacesPayload,
    setData,
    loading,
    error,
    reload,
  } = useAsyncResource(loadWorkspaces, { workspaces: [] });
  const workspaces = useMemo(() => workspacesPayload?.workspaces ?? [], [workspacesPayload]);
  const [selectedResourceId, setSelectedResourceId] = useState('');
  const activeWorkspaceId = selectedResourceId || workspaces[0]?.workspace_id || '';
  const [workspaceTrees, setWorkspaceTrees] = useState({});
  const [expandedNodes, setExpandedNodes] = useState({});
  const [workspaceDetails, setWorkspaceDetails] = useState({});
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [createError, setCreateError] = useState('');
  const [createPending, setCreatePending] = useState(false);

  async function handleSelectResource(id) {
    setSelectedResourceId(id);

    if (workspaces.some((workspace) => workspace.workspace_id === id)) {
      if (!workspaceTrees[id]) {
        const treePayload = await api.getWorkspaceTree(id);
        setWorkspaceTrees((current) => ({ ...current, [id]: treePayload.entries ?? [] }));
      }
      setWorkspaceDetails((current) => ({
        ...current,
        [id]: {
          title: workspaces.find((workspace) => workspace.workspace_id === id)?.name ?? id,
          type_label: 'Workspace',
          path: workspaces.find((workspace) => workspace.workspace_id === id)?.root_path ?? '',
          description: `状态：${workspaces.find((workspace) => workspace.workspace_id === id)?.status ?? 'unknown'}`,
          bindings: ['独立产品级 Workspace', '在创建 Session 时显式绑定'],
          preview_kind: 'note',
          preview: '该 Workspace 承载文件树、文件内容和执行上下文，不承载 Team 能力配置。',
        },
      }));
      return;
    }

    const [workspaceId, ...rest] = id.split(':');
    const path = rest.join(':');
    const filePayload = await api.getWorkspaceFile(workspaceId, path);
    setWorkspaceDetails((current) => ({
      ...current,
      [id]: {
        title: path.split('/').pop() ?? path,
        type_label: 'Workspace File',
        path,
        description: '实时读取自后端 workspace file API',
        bindings: [`workspace_id: ${workspaceId}`],
        preview_kind: 'code',
        preview: filePayload.content,
      },
    }));
  }

  async function handleExpandDirectory(node) {
    if (expandedNodes[node.id]) {
      setExpandedNodes((current) => ({ ...current, [node.id]: false }));
      return;
    }

    const [workspaceId, ...rest] = node.id.split(':');
    const path = rest.join(':');
    const treePayload = await api.getWorkspaceTree(workspaceId, path);
    setWorkspaceTrees((current) => ({
      ...current,
      [node.id]: treePayload.entries ?? [],
    }));
    setExpandedNodes((current) => ({ ...current, [node.id]: true }));
  }

  async function handleCreateWorkspace(payload) {
    setCreatePending(true);
    setCreateError('');

    try {
      const created = await api.createWorkspace(payload);
      const nextPayload = await loadWorkspaces();
      setData(nextPayload);
      setSelectedResourceId(created.workspace_id);
      setWorkspaceTrees((current) => ({
        ...current,
        [created.workspace_id]: current[created.workspace_id] ?? [],
      }));
      setWorkspaceDetails((current) => ({
        ...current,
        [created.workspace_id]: {
          title: created.name,
          type_label: 'Workspace',
          path: created.root_path,
          description: `状态：${created.status ?? 'unknown'}`,
          bindings: ['独立产品级 Workspace', '在创建 Session 时显式绑定'],
          preview_kind: 'note',
          preview: '选择左侧文件树中的文件查看内容。',
        },
      }));
      setIsCreateOpen(false);
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : '创建 workspace 失败');
    } finally {
      setCreatePending(false);
    }
  }

  const workspaceNodes = useMemo(
    () =>
      workspaces.map((workspace) => ({
        ...workspace,
        files: buildTreeNodes(
          workspace.workspace_id,
          workspaceTrees[workspace.workspace_id] ?? [],
          workspaceTrees,
          expandedNodes,
        ),
      })),
    [expandedNodes, workspaceTrees, workspaces],
  );

  const detail = useMemo(() => {
    if (workspaceDetails[activeWorkspaceId]) {
      return workspaceDetails[activeWorkspaceId];
    }
    const workspace = workspaces.find((item) => item.workspace_id === activeWorkspaceId);
    if (!workspace) return null;
    return {
      title: workspace.name,
      type_label: 'Workspace',
      path: workspace.root_path,
      description: `状态：${workspace.status}`,
      bindings: ['独立产品级 Workspace', '在创建 Session 时显式绑定'],
      preview_kind: 'note',
      preview: '选择左侧文件树中的文件查看内容。',
    };
  }, [activeWorkspaceId, workspaceDetails, workspaces]);

  return (
    <div className="workspace-page">
      {loading ? (
        <div className="workspace-loading">正在加载 workspace...</div>
      ) : error ? (
        <div className="workspace-loading">
          <p>{error}</p>
          <button type="button" className="workspace-primary-btn" onClick={() => void reload()}>
            重试
          </button>
        </div>
      ) : (
        <>
          <WorkspaceBrowser
            workspaces={workspaceNodes}
            selectedResourceId={activeWorkspaceId}
            isCreateOpen={isCreateOpen}
            createPending={createPending}
            createError={createError}
            onOpenCreate={() => {
              setCreateError('');
              setIsCreateOpen((current) => !current);
            }}
            onCreateWorkspace={(payload) => {
              void handleCreateWorkspace(payload);
            }}
            onSelectResource={(id) => {
              void handleSelectResource(id);
            }}
            onExpandDirectory={(node) => {
              void handleExpandDirectory(node);
            }}
          />
          <WorkspaceDetailPanel detail={detail} />
        </>
      )}
    </div>
  );
}
