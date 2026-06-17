import { FolderGit2 } from 'lucide-react';
import './RuntimePanel.css';

export default function RuntimePanel({
  runtime,
  onCancelSession,
  onResolveWaitingItem,
  cancelPending,
  waitingActionId,
}) {
  return (
    <div className="runtime-panel">
      <div className="runtime-header">
        <h3>运行态 (Runtime)</h3>
      </div>

      <div className="runtime-content">
        {!runtime ? (
          <div className="runtime-placeholder">
            <FolderGit2 size={48} className="placeholder-icon" />
            <p>选择一个会话后查看当前运行态。</p>
          </div>
        ) : (
          <>
            <section className="runtime-section">
              <h4>Session</h4>
              <p>标题：{runtime.session_title}</p>
              <p>状态：{runtime.session_status}</p>
              <p>Team：{runtime.session_team}</p>
              <button
                type="button"
                className="runtime-action-btn"
                onClick={onCancelSession}
                disabled={cancelPending}
                aria-label="取消当前运行"
              >
                {cancelPending ? '取消中...' : '取消当前运行'}
              </button>
            </section>

            <section className="runtime-section">
              <h4>Workspace 绑定</h4>
              <p>Session Workspace：{runtime.session_workspace}</p>
            </section>

            <section className="runtime-section">
              <h4>Runtime</h4>
              <p>Agent：{runtime.agent_status}</p>
              <p>Task：{runtime.task_status}</p>
            </section>

            <section className="runtime-section">
              <h4>Waiting</h4>
              {runtime.waiting_items.length === 0 ? <p>暂无 waiting item</p> : null}
              {runtime.waiting_items.map((item) => (
                <div key={item.waiting_id} className="runtime-waiting-item">
                  <p>{item.title} · {item.status}</p>
                  {item.message ? <p>{item.message}</p> : null}
                  <div className="runtime-action-row">
                    <button
                      type="button"
                      className="runtime-action-btn"
                      onClick={() => onResolveWaitingItem?.(item.waiting_id, true)}
                      disabled={waitingActionId === item.waiting_id}
                      aria-label={`批准 ${item.waiting_id}`}
                    >
                      批准
                    </button>
                    <button
                      type="button"
                      className="runtime-action-btn runtime-action-btn-secondary"
                      onClick={() => onResolveWaitingItem?.(item.waiting_id, false)}
                      disabled={waitingActionId === item.waiting_id}
                      aria-label={`拒绝 ${item.waiting_id}`}
                    >
                      拒绝
                    </button>
                  </div>
                </div>
              ))}
            </section>

            <section className="runtime-section">
              <h4>Plan / Summary</h4>
              <p>{runtime.plan_steps > 0 ? `${runtime.plan_steps} 个步骤` : '暂无计划'}</p>
              <p>{runtime.current_summary}</p>
            </section>

            <section className="runtime-section">
              <h4>Agent Statuses</h4>
              {runtime.agent_statuses.map((agent) => (
                <p key={agent.agent_id}>{agent.role} · {agent.agent_id} · {agent.status}</p>
              ))}
            </section>
          </>
        )}
      </div>
    </div>
  );
}
