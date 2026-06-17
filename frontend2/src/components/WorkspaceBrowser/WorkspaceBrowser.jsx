import {
  ChevronDown,
  ChevronRight,
  FileCode2,
  FolderClosed,
  FolderOpen,
  FolderKanban,
} from 'lucide-react';
import { useState } from 'react';
import './WorkspaceBrowser.css';

export default function WorkspaceBrowser({
  workspaces,
  selectedResourceId,
  isCreateOpen,
  createPending,
  createError,
  onOpenCreate,
  onCreateWorkspace,
  onSelectResource,
  onExpandDirectory,
}) {
  const [expandedKeys, setExpandedKeys] = useState(() => new Set(['workspace:workspace-1']));
  const [draftName, setDraftName] = useState('');
  const [draftDescription, setDraftDescription] = useState('');

  function toggleNode(key) {
    setExpandedKeys((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  function handleSubmit(event) {
    event.preventDefault();
    onCreateWorkspace?.({
      name: draftName.trim(),
      description: draftDescription.trim(),
    });
    setDraftName('');
    setDraftDescription('');
  }

  function renderFileNodes(nodes, depth) {
    return nodes.map((node) => {
      const isDirectory = node.type === 'directory';
      const nodeKey = `file:${node.id}`;
      const isExpanded = expandedKeys.has(nodeKey);
      const isSelected = node.id === selectedResourceId;

      return (
        <div key={node.id} className="explorer-node">
          <button
            type="button"
            className={`explorer-row ${isSelected ? 'selected' : ''}`}
            style={{ '--tree-depth': depth }}
            onClick={() => {
              if (isDirectory) {
                toggleNode(nodeKey);
                if (!isExpanded) {
                  onExpandDirectory?.(node);
                }
                return;
              }
              onSelectResource(node.id);
            }}
          >
            <span className="explorer-indent" />
            {isDirectory ? (
              <span className="explorer-chevron">{isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}</span>
            ) : (
              <span className="explorer-chevron spacer" />
            )}
            <span className="explorer-icon">
              {isDirectory ? isExpanded ? <FolderOpen size={16} /> : <FolderClosed size={16} /> : <FileCode2 size={16} />}
            </span>
            <span className="explorer-label">{node.name}</span>
          </button>
          {isDirectory && isExpanded ? renderFileNodes(node.children ?? [], depth + 1) : null}
        </div>
      );
    });
  }

  return (
    <aside className="workspace-browser-nav">
      <div className="workspace-browser-nav-header">
        <div>
          <h2>Workspace</h2>
          <p>独立产品资源</p>
        </div>
        <button type="button" className="workspace-primary-btn" onClick={onOpenCreate}>
          新建
        </button>
      </div>
      {isCreateOpen ? (
        <form className="workspace-create-form" onSubmit={handleSubmit}>
          <label className="workspace-field">
            <span>Workspace 名称</span>
            <input
              type="text"
              value={draftName}
              onChange={(event) => setDraftName(event.target.value)}
              placeholder="例如：Project Alpha"
              required
            />
          </label>
          <label className="workspace-field">
            <span>Workspace 描述</span>
            <textarea
              value={draftDescription}
              onChange={(event) => setDraftDescription(event.target.value)}
              placeholder="这个 workspace 用来做什么"
              rows={3}
            />
          </label>
          {createError ? <p className="workspace-form-error">{createError}</p> : null}
          <button type="submit" className="workspace-primary-btn" disabled={createPending || !draftName.trim()}>
            {createPending ? '创建中...' : '创建 workspace'}
          </button>
        </form>
      ) : null}
      <span className="workspace-count">{workspaces.length} 个 workspace</span>

      <div className="workspace-browser-tree">
        {workspaces.map((workspace) => {
          const workspaceKey = `workspace:${workspace.workspace_id}`;
          const isWorkspaceExpanded = expandedKeys.has(workspaceKey);
          const isWorkspaceSelected = workspace.workspace_id === selectedResourceId;

          return (
            <div key={workspace.workspace_id} className="explorer-group">
              <div className={`explorer-row source-level ${isWorkspaceSelected ? 'selected' : ''}`}>
                <button type="button" className="toggle-btn" onClick={() => toggleNode(workspaceKey)}>
                  {isWorkspaceExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                </button>
                <button type="button" className="item-btn" onClick={() => onSelectResource(workspace.workspace_id)}>
                  <span className="explorer-icon"><FolderKanban size={16} /></span>
                  <span className="explorer-label">{workspace.name}</span>
                </button>
              </div>

              {isWorkspaceExpanded ? (
                <div className="source-children">
                  <div className="explorer-row section-level">
                    <span className="section-label">
                      <FileCode2 size={14} />
                      Files
                      <span className="explorer-meta">{workspace.files.length}</span>
                    </span>
                  </div>
                  <div className="file-tree">{renderFileNodes(workspace.files ?? [], 1)}</div>
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </aside>
  );
}
