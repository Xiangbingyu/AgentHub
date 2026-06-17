import { Plus, Search } from 'lucide-react';
import { useState } from 'react';
import PanelHeader from '../ui/PanelHeader';
import PrimaryButton from '../ui/PrimaryButton';
import './SessionList.css';

export default function SessionList({
  sessions,
  activeSessionId,
  teams,
  workspaces,
  isCreateOpen,
  createPending,
  createError,
  createDisabled,
  onOpenCreate,
  onCreateSession,
  onSelectSession,
}) {
  const [draftName, setDraftName] = useState('');
  const defaultWorkspaceId = workspaces[0]?.workspace_id ?? '';
  const defaultTeamId = teams[0]?.team_id ?? '';
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState(defaultWorkspaceId);
  const [selectedTeamId, setSelectedTeamId] = useState(defaultTeamId);
  const effectiveWorkspaceId = selectedWorkspaceId || defaultWorkspaceId;
  const effectiveTeamId = selectedTeamId || defaultTeamId;

  function handleSubmit(event) {
    event.preventDefault();
    onCreateSession?.({
      name: draftName.trim(),
      workspace_id: effectiveWorkspaceId,
      team_id: effectiveTeamId,
    });
    setDraftName('');
  }

  return (
    <aside className="session-list-container">
      <PanelHeader
        title="Sessions"
        subtitle="当前 Session 列表，可快速搜索和创建新的会话。"
        action={
          <PrimaryButton icon={Plus} onClick={onOpenCreate}>
            新建
          </PrimaryButton>
        }
      >
        <span className="panel-header-meta">{sessions.length} 个 Session</span>
        <div className="search-bar">
          <Search size={16} className="search-icon" />
          <input type="text" placeholder="搜索会话（Mock）" readOnly />
        </div>
        {isCreateOpen ? (
          <form className="session-create-form" onSubmit={handleSubmit}>
            <label className="session-field">
              <span>Session 名称</span>
              <input
                type="text"
                value={draftName}
                onChange={(event) => setDraftName(event.target.value)}
                placeholder="例如：实现 callback 主链"
                required
              />
            </label>
            <label className="session-field">
              <span>绑定 Workspace</span>
              <select
                value={effectiveWorkspaceId}
                onChange={(event) => setSelectedWorkspaceId(event.target.value)}
                disabled={createDisabled}
              >
                <option value="">选择 workspace</option>
                {workspaces.map((workspace) => (
                  <option key={workspace.workspace_id} value={workspace.workspace_id}>
                    {workspace.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="session-field">
              <span>绑定 Team</span>
              <select
                value={effectiveTeamId}
                onChange={(event) => setSelectedTeamId(event.target.value)}
                disabled={createDisabled}
              >
                <option value="">选择 team</option>
                {teams.map((team) => (
                  <option key={team.team_id} value={team.team_id}>
                    {team.name}
                  </option>
                ))}
              </select>
            </label>
            {createError ? <p className="session-form-error">{createError}</p> : null}
            <PrimaryButton
              type="submit"
              disabled={
                createPending ||
                createDisabled ||
                !draftName.trim() ||
                !effectiveWorkspaceId ||
                !effectiveTeamId
              }
            >
              {createPending ? '创建中...' : '新建 Session'}
            </PrimaryButton>
          </form>
        ) : null}
      </PanelHeader>

      <div className="session-list">
        {sessions.length === 0 ? (
          <div className="session-state">暂无会话</div>
        ) : (
          sessions.map((session) => (
            <div
              key={session.session_id}
              className={`session-item ${session.session_id === activeSessionId ? 'active' : ''}`}
              onClick={() => onSelectSession(session.session_id)}
            >
              <div className="avatar">A</div>
              <div className="info">
                <div className="info-top">
                  <span className="name">{session.title}</span>
                  <span className="time">{session.updated_at}</span>
                </div>
                <div className="info-bottom">{session.summary}</div>
              </div>
            </div>
          ))
        )}
      </div>
    </aside>
  );
}
