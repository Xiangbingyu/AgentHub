import { ChevronLeft, ChevronRight, FolderGit2 } from 'lucide-react';
import './RuntimePanel.css';

export default function RuntimePanel({ runtime, collapsed, onToggleCollapse }) {
  return (
    <div className={`runtime-panel ${collapsed ? 'collapsed' : ''}`}>
      <div className="runtime-header">
        <button
          type="button"
          className="runtime-collapse-btn"
          onClick={onToggleCollapse}
          aria-label={collapsed ? '展开运行态' : '收起运行态'}
          title={collapsed ? '展开运行态' : '收起运行态'}
        >
          {collapsed ? <ChevronLeft size={18} /> : <ChevronRight size={18} />}
        </button>
        {!collapsed ? <h3>运行态 (Runtime)</h3> : null}
      </div>

      {!collapsed ? (
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
              </section>

              <section className="runtime-section">
                <h4>Workspace 绑定</h4>
                <p>Session Workspace：{runtime.session_workspace}</p>
                <p>Source Workspace：{runtime.source_workspace}</p>
              </section>

              <section className="runtime-section">
                <h4>Runtime</h4>
                <p>Agent：{runtime.agent_status}</p>
                <p>Task：{runtime.task_status}</p>
              </section>

              <section className="runtime-section">
                <h4>Plan</h4>
                <p>{runtime.plan_steps > 0 ? `${runtime.plan_steps} 个步骤` : '暂无计划'}</p>
              </section>
            </>
          )}
        </div>
      ) : null}
    </div>
  );
}
