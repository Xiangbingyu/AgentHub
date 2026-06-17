import { Plus, Users } from 'lucide-react';
import PanelHeader from '../ui/PanelHeader';
import PrimaryButton from '../ui/PrimaryButton';
import './TeamList.css';

export default function TeamList({ teams, activeTeamId, onSelectTeam }) {
  return (
    <aside className="team-list-container">
      <PanelHeader
        title="Teams"
        subtitle="Product Team 列表。当前只做 mock 展示和创建入口外观。"
        action={
          <PrimaryButton icon={Plus}>
            新建
          </PrimaryButton>
        }
      >
        <span className="panel-header-meta">{teams.length} 个 Team</span>
      </PanelHeader>

      <div className="team-list-body">
        {teams.map((team) => (
          <button
            key={team.team_id}
            type="button"
            className={`team-card ${team.team_id === activeTeamId ? 'active' : ''}`}
            onClick={() => onSelectTeam(team.team_id)}
          >
            <div className="team-card-top">
              <div className="team-avatar">
                <Users size={18} />
              </div>
              <div className="team-card-text">
                <div className="team-card-name">{team.name}</div>
                <div className="team-card-meta">Leader: {team.leader_agent_id}</div>
              </div>
              {team.is_default ? <span className="team-badge">Default</span> : null}
            </div>
            <div className="team-card-desc">{team.description}</div>
          </button>
        ))}
      </div>
    </aside>
  );
}
