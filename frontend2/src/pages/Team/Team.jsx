import { useCallback, useMemo, useState } from 'react';
import { useAsyncResource } from '../../hooks/useAsyncResource';
import { api } from '../../utils/api';
import TeamDetailPanel from '../../components/TeamDetailPanel/TeamDetailPanel';
import TeamList from '../../components/TeamList/TeamList';
import './Team.css';

export default function Team() {
  const loadTeams = useCallback(() => api.listTeams(), []);
  const {
    data: teamsPayload,
    loading,
    error,
    reload,
  } = useAsyncResource(loadTeams, { teams: [] });
  const teams = useMemo(() => teamsPayload?.teams ?? [], [teamsPayload]);
  const [selectedTeamId, setSelectedTeamId] = useState('');
  const activeTeamId = selectedTeamId || teams[0]?.team_id || '';
  const activeTeam = useMemo(
    () => teams.find((team) => team.team_id === activeTeamId) ?? teams[0] ?? null,
    [activeTeamId, teams],
  );

  async function handleCreateTeam(payload) {
    await api.createTeam(payload);
    await reload();
  }

  return (
    <div className="team-page">
      {loading ? (
        <div className="team-loading">正在加载 team...</div>
      ) : error ? (
        <div className="team-loading">
          <p>{error}</p>
          <button type="button" className="team-create-btn" onClick={() => void reload()}>
            重试
          </button>
        </div>
      ) : (
        <>
          <TeamList teams={teams} activeTeamId={activeTeam?.team_id} onSelectTeam={setSelectedTeamId} />
          <TeamDetailPanel team={activeTeam} onCreateTeam={handleCreateTeam} />
        </>
      )}
    </div>
  );
}
