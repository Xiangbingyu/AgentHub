import { useState } from 'react';
import {
  Boxes,
  ChevronDown,
  ChevronRight,
  FileCode2,
  FolderClosed,
  FolderOpen,
  FolderGit2,
  GitBranch,
} from 'lucide-react';
import './WorkspaceBrowser.css';

export default function WorkspaceBrowser({
  sourceWorkspaces,
  selectedResourceId,
  onSelectResource,
  onExpandDirectory,
  onExpandSessionWorkspace,
  onCreateSource,
}) {
  const [expandedKeys, setExpandedKeys] = useState(() => {
    const keys = new Set();
    const firstSource = sourceWorkspaces[0];
    if (firstSource) {
      keys.add(`source:${firstSource.source_workspace_id}`);
      keys.add(`code:${firstSource.source_workspace_id}`);
    }
    return keys;
  });

  function toggleNode(key) {
    setExpandedKeys((current) => {
      const next = new Set(current);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
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
              <span className="explorer-chevron" aria-hidden="true">
                {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
              </span>
            ) : (
              <span className="explorer-chevron spacer" aria-hidden="true" />
            )}
            <span className="explorer-icon" aria-hidden="true">
              {isDirectory ? (
                isExpanded ? <FolderOpen size={16} /> : <FolderClosed size={16} />
              ) : (
                <FileCode2 size={16} />
              )}
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
          <p>资源导航</p>
        </div>
        <button type="button" className="workspace-primary-btn" onClick={() => onCreateSource?.()}>
          新建
        </button>
      </div>
      <span className="workspace-count">{sourceWorkspaces.length} 个 source workspace</span>

      <div className="workspace-browser-tree">
        {sourceWorkspaces.map((source) => {
          const sourceKey = `source:${source.source_workspace_id}`;
          const codeKey = `code:${source.source_workspace_id}`;
          const branchKey = `branch:${source.source_workspace_id}`;
          const isSourceExpanded = expandedKeys.has(sourceKey);
          const isCodeExpanded = expandedKeys.has(codeKey);
          const isBranchExpanded = expandedKeys.has(branchKey);
          const isSourceSelected = source.source_workspace_id === selectedResourceId;

          return (
            <div key={source.source_workspace_id} className="explorer-group">
              <div className={`explorer-row source-level ${isSourceSelected ? 'selected' : ''}`}>
                <button
                  type="button"
                  className="toggle-btn"
                  onClick={() => toggleNode(sourceKey)}
                  aria-label={`${isSourceExpanded ? '收起' : '展开'} ${source.name}`}
                >
                  {isSourceExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                </button>
                <button
                  type="button"
                  className="item-btn"
                  onClick={() => onSelectResource(source.source_workspace_id)}
                >
                  <span className="explorer-icon" aria-hidden="true">
                    <Boxes size={16} />
                  </span>
                  <span className="explorer-label">{source.name}</span>
                </button>
              </div>

              {isSourceExpanded ? (
                <div className="source-children">
                  {/* 真源项目代码（最终代码真源） */}
                  <div className="explorer-group">
                    <div className="explorer-row section-level">
                      <button
                        type="button"
                        className="toggle-btn"
                        onClick={() => toggleNode(codeKey)}
                        aria-label={`${isCodeExpanded ? '收起' : '展开'}源代码`}
                      >
                        {isCodeExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                      </button>
                      <span className="section-label">
                        <FileCode2 size={14} />
                        Source Workspace
                      </span>
                    </div>
                    {isCodeExpanded ? (
                      <div className="file-tree">{renderFileNodes(source.files ?? [], 1)}</div>
                    ) : null}
                  </div>

                  {/* 基于真源派生的 session workspace */}
                  <div className="explorer-group">
                    <div className="explorer-row section-level">
                      <button
                        type="button"
                        className="toggle-btn"
                        onClick={() => toggleNode(branchKey)}
                        aria-label={`${isBranchExpanded ? '收起' : '展开'}派生工作区`}
                      >
                        {isBranchExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                      </button>
                      <span className="section-label">
                        <FolderGit2 size={14} />
                        Session Workspaces
                        <span className="explorer-meta">{source.session_workspaces.length}</span>
                      </span>
                    </div>
                    {isBranchExpanded ? (
                      <div className="session-list-tree">
                        {source.session_workspaces.map((sessionWorkspace) => {
                          const sessionKey = `session:${sessionWorkspace.session_workspace_id}`;
                          const isSessionExpanded = expandedKeys.has(sessionKey);
                          const isSessionSelected =
                            sessionWorkspace.session_workspace_id === selectedResourceId;

                          return (
                            <div key={sessionWorkspace.session_workspace_id} className="explorer-group">
                              <div className={`explorer-row session-level ${isSessionSelected ? 'selected' : ''}`}>
                                <button
                                  type="button"
                                  className="toggle-btn"
                                  onClick={() => {
                                    toggleNode(sessionKey);
                                    if (!isSessionExpanded) {
                                      onExpandSessionWorkspace?.(sessionWorkspace.session_workspace_id);
                                    }
                                  }}
                                  aria-label={`${isSessionExpanded ? '收起' : '展开'} ${sessionWorkspace.name}`}
                                >
                                  {isSessionExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                                </button>
                                <button
                                  type="button"
                                  className="item-btn"
                                  onClick={() => onSelectResource(sessionWorkspace.session_workspace_id)}
                                >
                                  <span className="explorer-icon" aria-hidden="true">
                                    <GitBranch size={16} />
                                  </span>
                                  <span className="explorer-label">{sessionWorkspace.name}</span>
                                </button>
                              </div>

                              {isSessionExpanded ? (
                                <div className="file-tree">
                                  {renderFileNodes(sessionWorkspace.files ?? [], 2)}
                                </div>
                              ) : null}
                            </div>
                          );
                        })}
                      </div>
                    ) : null}
                  </div>
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </aside>
  );
}
