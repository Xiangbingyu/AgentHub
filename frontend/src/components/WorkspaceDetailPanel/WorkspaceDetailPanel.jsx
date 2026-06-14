import { FileCode2, GitBranch, Info } from 'lucide-react';
import './WorkspaceDetailPanel.css';

export default function WorkspaceDetailPanel({ detail }) {
  return (
    <section className="workspace-detail">
      <div className="workspace-detail-header">
        <div>
          <h3>{detail ? detail.title : '未选择资源'}</h3>
          <p>{detail ? detail.type_label : '从左侧资源树中选择一项查看详情'}</p>
        </div>
        {detail ? <span className="workspace-detail-tag">{detail.type_label}</span> : null}
      </div>

      <div className="workspace-detail-content">
        {!detail ? (
          <div className="workspace-detail-empty">
            选择左侧资源后，这里会显示路径、绑定关系与内容预览。
          </div>
        ) : (
          <>
            <div className="workspace-detail-cards">
              <section className="detail-card">
                <div className="detail-card-title">
                  <Info size={16} />
                  <span>基本信息</span>
                </div>
                <p>路径：{detail.path}</p>
                <p>描述：{detail.description}</p>
              </section>

              <section className="detail-card">
                <div className="detail-card-title">
                  <GitBranch size={16} />
                  <span>绑定关系</span>
                </div>
                {detail.bindings.map((binding) => (
                  <p key={binding}>{binding}</p>
                ))}
              </section>
            </div>

            <section className="detail-card detail-preview-card">
              <div className="detail-card-title">
                <FileCode2 size={16} />
                <span>内容预览</span>
              </div>
              <div className="detail-preview-body">
                {detail.preview_kind === 'code' ? (
                  <pre className="detail-code-preview">{detail.preview}</pre>
                ) : (
                  <div className="detail-note-preview">{detail.preview}</div>
                )}
              </div>
            </section>
          </>
        )}
      </div>
    </section>
  );
}
