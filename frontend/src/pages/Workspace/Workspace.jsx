import { useCallback, useEffect, useState } from 'react';
import WorkspaceBrowser from '../../components/WorkspaceBrowser/WorkspaceBrowser';
import WorkspaceDetailPanel from '../../components/WorkspaceDetailPanel/WorkspaceDetailPanel';
import Modal from '../../components/Modal/Modal';
import {
  listSourceWorkspaces,
  getWorkspacePage,
  getWorkspaceTree,
  createSourceWorkspace,
} from '../../utils/api';
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

// 在 source 树中按 id 注入某目录的子节点（不可变更新）
function injectChildren(sources, sourceId, dirId, children) {
  function walk(nodes) {
    return nodes.map((node) => {
      if (node.id === dirId) {
        return { ...node, children };
      }
      if (node.children) {
        return { ...node, children: walk(node.children) };
      }
      return node;
    });
  }
  return sources.map((source) =>
    source.source_workspace_id === sourceId
      ? { ...source, files: walk(source.files ?? []) }
      : source,
  );
}

export default function Workspace() {
  const [sources, setSources] = useState([]);
  const [selectedResourceId, setSelectedResourceId] = useState('');
  const [detailsById, setDetailsById] = useState({});

  // 建 source workspace 弹窗状态
  const [createOpen, setCreateOpen] = useState(false);
  const [newName, setNewName] = useState('');
  const [newPath, setNewPath] = useState('');
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState('');

  const loadSources = async () => {
    let rows;
    try {
      rows = await listSourceWorkspaces();
    } catch {
      setSources([]);
      return [];
    }
    const enriched = await Promise.all(
      rows.map(async (source) => {
        const sourceId = source.source_workspace_id;
        let page;
        try {
          page = await getWorkspacePage(sourceId);
        } catch {
          page = {};
        }
        return {
          ...source,
          files: (page.tree ?? []).map((entry) => toFileNode(sourceId, entry)),
          session_workspaces: page.session_workspaces ?? [],
        };
      }),
    );
    setSources(enriched);
    setSelectedResourceId((current) => current || enriched[0]?.source_workspace_id || '');
    const details = {};
    enriched.forEach((source) => {
      details[source.source_workspace_id] = {
        title: source.name,
        type_label: 'Source Workspace · 真源',
        path: source.root_path,
        description: `状态：${source.status}`,
        bindings: [`派生 ${source.session_workspaces.length} 个 session workspace`],
        preview_kind: 'note',
        preview: '选择文件查看路径与详情。',
      };
    });
    setDetailsById((current) => ({ ...details, ...current }));
    return enriched;
  };

  // 启动：拉 source workspace 列表 + 每个 source 的根层 tree + 派生 session workspaces
  useEffect(() => {
    // loadSources 的 setState 均在 await 之后异步触发，非同步级联渲染
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadSources();
  }, []);

  function handleCreateSource() {
    if (!newName.trim() || !newPath.trim()) {
      setCreateError('请填写名称与本地目录路径');
      return;
    }
    setCreating(true);
    setCreateError('');
    createSourceWorkspace({ name: newName.trim(), root_path: newPath.trim() })
      .then(() => {
        setCreateOpen(false);
        setNewName('');
        setNewPath('');
        return loadSources();
      })
      .catch((err) => setCreateError(err.message || '创建失败，请确认目录存在'))
      .finally(() => setCreating(false));
  }

  // 目录展开：按需拉该层 tree 并注入 children
  const handleExpandDirectory = useCallback(
    (node) => {
      if (node.children) {
        return;
      }
      const [sourceId] = node.id.split(':');
      getWorkspaceTree(sourceId, node.path)
        .then((entries) => {
          const children = entries.map((entry) => toFileNode(sourceId, entry));
          setSources((current) =>
            injectChildren(current, sourceId, node.id, children),
          );
        })
        .catch(() => undefined);
    },
    [],
  );

  // 选中文件/节点：构造一个最小详情
  function handleSelectResource(id) {
    setSelectedResourceId(id);
    setDetailsById((current) => {
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

  const detail = detailsById[selectedResourceId] ?? null;

  return (
    <div className="workspace-page">
      <WorkspaceBrowser
        sourceWorkspaces={sources}
        selectedResourceId={selectedResourceId}
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
