import { useCallback, useEffect, useState } from 'react';
import WorkspaceBrowser from '../../components/WorkspaceBrowser/WorkspaceBrowser';
import WorkspaceDetailPanel from '../../components/WorkspaceDetailPanel/WorkspaceDetailPanel';
import {
  listSourceWorkspaces,
  getWorkspacePage,
  getWorkspaceTree,
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

  // 启动：拉 source workspace 列表，并为每个 source 拉根层 tree + 派生 session workspaces
  useEffect(() => {
    let cancelled = false;
    listSourceWorkspaces()
      .then(async (rows) => {
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
        if (cancelled) {
          return;
        }
        setSources(enriched);
        setSelectedResourceId(
          (current) => current || enriched[0]?.source_workspace_id || '',
        );
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
        setDetailsById(details);
      })
      .catch(() => {
        if (!cancelled) {
          setSources([]);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

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
      />
      <WorkspaceDetailPanel detail={detail} />
    </div>
  );
}
