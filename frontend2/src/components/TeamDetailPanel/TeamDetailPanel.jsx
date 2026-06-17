import { Bot, Cpu, ShieldCheck, Wrench } from 'lucide-react';
import { useState } from 'react';
import './TeamDetailPanel.css';

export default function TeamDetailPanel({ team, onCreateTeam }) {
  const [name, setName] = useState('');
  const [leaderAgentId, setLeaderAgentId] = useState('');
  const [memberAgentIds, setMemberAgentIds] = useState('');

  async function handleCreate() {
    const members = memberAgentIds
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean);
    await onCreateTeam?.({
      name: name.trim(),
      leader_agent_id: leaderAgentId.trim(),
      member_agent_ids: members,
    });
    setName('');
    setLeaderAgentId('');
    setMemberAgentIds('');
  }

  return (
    <section className="team-detail">
      <div className="team-detail-header">
        <div>
          <h3>{team?.name ?? '未选择 Team'}</h3>
          <p>{team?.description ?? '选择左侧 Team 查看 leader、members 与能力边界。'}</p>
        </div>
        {team ? <span className="team-detail-tag">Product Team</span> : null}
      </div>

      <div className="team-detail-content">
        {!team ? (
          <div className="team-detail-empty">当前没有选中的 Team。</div>
        ) : (
          <>
            <div className="team-detail-grid">
              <section className="team-section">
                <div className="team-section-title"><Bot size={16} /><span>Leader</span></div>
                <p>{team.leader_agent_id}</p>
              </section>

              <section className="team-section">
                <div className="team-section-title"><ShieldCheck size={16} /><span>Members</span></div>
                {team.member_agent_ids.map((member) => (
                  <p key={member}>{member}</p>
                ))}
              </section>
            </div>

            <div className="team-detail-grid">
              <section className="team-section">
                <div className="team-section-title"><Cpu size={16} /><span>Model Config</span></div>
                <p>当前后端第一期还没有对外暴露 team 级 model config 详情。</p>
                <p>这里保留为页面壳，后续可在 team detail 接口完善后补充。</p>
              </section>

              <section className="team-section">
                <div className="team-section-title"><Wrench size={16} /><span>Capabilities</span></div>
                <p>tool policy keys: {Object.keys(team.enabled_tool_policy ?? {}).join(', ') || '—'}</p>
                <p>mcps: {(team.enabled_mcp_refs ?? []).join(', ') || '—'}</p>
                <p>skills: {(team.enabled_skill_refs ?? []).join(', ') || '—'}</p>
              </section>
            </div>

            <section className="team-section team-create-mock">
              <div className="team-section-title"><Bot size={16} /><span>Create Team（Mock）</span></div>
              <div className="team-create-fields">
                <input type="text" placeholder="Team 名称" value={name} onChange={(event) => setName(event.target.value)} />
                <input
                  type="text"
                  placeholder="Leader Agent ID"
                  value={leaderAgentId}
                  onChange={(event) => setLeaderAgentId(event.target.value)}
                />
                <textarea
                  placeholder="Member Agent IDs，逗号分隔"
                  value={memberAgentIds}
                  onChange={(event) => setMemberAgentIds(event.target.value)}
                />
              </div>
              <button type="button" className="team-submit-btn" onClick={() => void handleCreate()}>
                创建 Team
              </button>
            </section>
          </>
        )}
      </div>
    </section>
  );
}
