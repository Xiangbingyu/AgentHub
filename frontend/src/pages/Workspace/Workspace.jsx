import { useCallback, useMemo, useState } from 'react';
import WorkspaceBrowser from '../../components/WorkspaceBrowser/WorkspaceBrowser';
import WorkspaceDetailPanel from '../../components/WorkspaceDetailPanel/WorkspaceDetailPanel';
import Modal from '../../components/Modal/Modal';
import {
  useListSourceWorkspacesQuery,
  useGetWorkspacePageQuery,
  useLazyGetWorkspaceTreeQuery,
  useCreateSourceWorkspaceMutation,
} from '../../store/api';
import './Workspace.css';

// 后端 tree 节点（{type,name,path}）→ 浏览器节点（带唯一 id 与 children 占位）
function toFileNode(sourceId, entry) {
  return {
    id: `${sourceId}:${entry.path}`,
    type: entry.type,
    name: entry.name,
    path: entry.path,
    children: entry.type === 'directory' ? null : undefined,
  };
}

// 按 nodeId→children 映射，递归注入按需展开的子节点（不可变更新）
function injectByMap(nodes, childrenMap) {
  return nodes.map((node) => {
    const injected = childrenMap[node.id];
    if (injected) {
      return { ...node, children: injectByMap(injected, childrenMap) };
    }
    if (node.children) {
      return { ...node, children: injectByMap(node.children, childrenMap) };
    }
    return node;
  });
}

export default function Workspace() {
  // 用户显式选中的资源（source / 文件节点 / session workspace）
  const [selectedResourceId, setSelectedResourceId] = useState('');
  // 用户显式切换的活动 source；未选时回退第一条（派生）
  const [pickedSourceId, setPickedSourceId] = useState('');
  // 目录按需展开注入的子节点：nodeId → children[]
  const [expandedChildren, setExpandedChildren] = useState({});
  const [trackedSourceId, setTrackedSourceId] = useState('');
  const [fileDetails, setFileDetails] = useState({});

  // 建 source workspace 弹窗状态
  const [createOpen, setCreateOpen] = useState(false);
  const [newName, setNewName] = useState('');
  const [newPath, setNewPath] = useState('');
  const [createError, setCreateError] = useState('');

  // source 列表：缓存命中立即出框架，后台 refetch
  const { data: sourceRows = [] } = useListSourceWorkspacesQuery();

  // 活动 source（派生：未选则取第一条）
  const activeSourceId = pickedSourceId || sourceRows[0]?.source_workspace_id || '';

  // 只拉选中 source 的 page（tree + 派生 session workspaces）
  const { data: activePage } = useGetWorkspacePageQuery(activeSourceId, {
    skip: !activeSourceId,
  });
  const [triggerTree] = useLazyGetWorkspaceTreeQuery();
  const [createSource, { isLoading: creating }] = useCreateSourceWorkspaceMutation();

  // 切换 source 时清空上一个 source 的展开缓存（渲染期同步，避免 effect 级联）
  if (trackedSourceId !== activeSourceId) {
    setTrackedSourceId(activeSourceId);
    setExpandedChildren({});
  }

  const effectiveSelectedId = selectedResourceId || activeSourceId;

  // 传给 WorkspaceBrowser 的 sources：仅活动 source 带 files/session_workspaces
  const sources = useMemo(() => {
    return sourceRows.map((source) => {
      if (source.source_workspace_id !== activeSourceId) {
        return { ...source, files: [], session_workspaces: [] };
      }
      const baseFiles = (activePage?.tree ?? []).map((entry) =>
        toFileNode(source.source_workspace_id, entry),
      );
      const files = injectByMap(baseFiles, expandedChildren);
      return {
        ...source,
        files,
        session_workspaces: activePage?.session_workspaces ?? [],
      };
    });
  }, [sourceRows, activeSourceId, activePage, expandedChildren]);

  const detailsById = useMemo(() => {
    const map = {};
    const active = sourceRows.find((s) => s.source_workspace_id === activeSourceId);
    if (active) {
      map[active.source_workspace_id] = {
        title: active.name,
        type_label: 'Source Workspace · 真源',
        path: active.root_path,
        description: `状态：${active.status}`,
        bindings: [`派生 ${activePage?.session_workspaces?.length ?? 0} 个 session workspace`],
        preview_kind: 'note',
        preview: '选择文件查看路径与详情。',
      };
    }
    return { ...map, ...fileDetails };
  }, [sourceRows, activeSourceId, activePage, fileDetails]);

  function handleCreateSource() {
    if (!newName.trim() || !newPath.trim()) {
      setCreateError('请填写名称与本地目录路径');
      return;
    }
    setCreateError('');
    createSource({ name: newName.trim(), root_path: newPath.trim() })
      .unwrap()
      .then(() => {
        setCreateOpen(false);
        setNewName('');
        setNewPath('');
      })
      .catch((err) =>
        setCreateError(err?.data?.detail || err?.error || '创建失败，请确认目录存在'),
      );
  }

  // 目录展开：按需拉该层 tree 并注入 children
  const handleExpandDirectory = useCallback(
    (node) => {
      if (node.children) {
        return;
      }
      const [sourceId] = node.id.split(':');
      triggerTree({ sourceId, path: node.path })
        .unwrap()
        .then((entries) => {
          const children = entries.map((entry) => toFileNode(sourceId, entry));
          setExpandedChildren((current) => ({ ...current, [node.id]: children }));
        })
        .catch(() => undefined);
    },
    [triggerTree],
  );

  // 选中文件/节点：source 行切换活动 source，文件节点构造最小详情
  function handleSelectResource(id) {
    setSelectedResourceId(id);
    if (sourceRows.some((s) => s.source_workspace_id === id)) {
      setPickedSourceId(id);
      return;
    }
    setFileDetails((current) => {
      if (current[id]) {
        return current;
      }
      const path = id.includes(':') ? id.split(':').slice(1).join(':') : id;
      return {
        ...current,
        [id]: {
          title: path.split('/').pop() || id,
          type_label: 'File · 派生/真源',
          path,
          description: '来自 workspace 文件树',
          bindings: [],
          preview_kind: 'note',
          preview: '内容预览待接入文件读取接口。',
        },
      };
    });
  }

  const detail = detailsById[effectiveSelectedId] ?? null;

  return (
    <div className="workspace-page">
      <WorkspaceBrowser
        sourceWorkspaces={sources}
        selectedResourceId={effectiveSelectedId}
        onSelectResource={handleSelectResource}
        onExpandDirectory={handleExpandDirectory}
        onCreateSource={() => {
          setCreateError('');
          setCreateOpen(true);
        }}
      />
      <WorkspaceDetailPanel detail={detail} />

      <Modal open={createOpen} title="新建 Source Workspace" onClose={() => setCreateOpen(false)}>
        {createError ? <div className="modal-error">{createError}</div> : null}
        <div className="modal-field">
          <label htmlFor="new-source-name">名称</label>
          <input
            id="new-source-name"
            type="text"
            value={newName}
            placeholder="例如：my-project"
            onChange={(event) => setNewName(event.target.value)}
          />
        </div>
        <div className="modal-field">
          <label htmlFor="new-source-path">本地目录路径（须已存在）</label>
          <input
            id="new-source-path"
            type="text"
            value={newPath}
            placeholder="例如：E:/projects/my-project"
            onChange={(event) => setNewPath(event.target.value)}
          />
        </div>
        <div className="modal-actions">
          <button type="button" className="modal-btn" onClick={() => setCreateOpen(false)}>
            取消
          </button>
          <button
            type="button"
            className="modal-btn primary"
            disabled={creating}
            onClick={handleCreateSource}
          >
            {creating ? '创建中…' : '创建'}
          </button>
        </div>
      </Modal>
    </div>
  );
}
