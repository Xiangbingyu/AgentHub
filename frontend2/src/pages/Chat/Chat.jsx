import { useCallback, useEffect, useMemo, useState } from 'react';
import { useAsyncResource } from '../../hooks/useAsyncResource';
import { api } from '../../utils/api';
import ChatPanel from '../../components/ChatPanel/ChatPanel';
import { renderContentBlocks } from '../../utils/message';
import RuntimePanel from '../../components/RuntimePanel/RuntimePanel';
import SessionList from '../../components/SessionList/SessionList';
import './Chat.css';

export default function Chat() {
  const loadSessions = useCallback(() => api.listSessions(), []);
  const {
    data: sessionsPayload,
    setData: setSessionsPayload,
    loading: sessionsLoading,
    error: sessionsError,
    reload: reloadSessions,
  } = useAsyncResource(loadSessions, { sessions: [] });
  const sessions = useMemo(() => sessionsPayload?.sessions ?? [], [sessionsPayload]);
  const [selectedSessionId, setSelectedSessionId] = useState('');
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [createError, setCreateError] = useState('');
  const [createPending, setCreatePending] = useState(false);
  const [cancelPending, setCancelPending] = useState(false);
  const [waitingActionId, setWaitingActionId] = useState('');
  const [optimisticMessages, setOptimisticMessages] = useState([]);
  const activeSessionId = selectedSessionId || sessions[0]?.session_id || '';

  const loadTeams = useCallback(() => api.listTeams(), []);
  const { data: teamsPayload, loading: teamsLoading } = useAsyncResource(loadTeams, { teams: [] });
  const teams = useMemo(() => teamsPayload?.teams ?? [], [teamsPayload]);

  const loadWorkspaces = useCallback(() => api.listWorkspaces(), []);
  const { data: workspacesPayload, loading: workspacesLoading } = useAsyncResource(loadWorkspaces, { workspaces: [] });
  const workspaces = useMemo(() => workspacesPayload?.workspaces ?? [], [workspacesPayload]);

  const loadDetail = useCallback(
    () => (activeSessionId ? api.getSessionDetail(activeSessionId) : Promise.resolve(null)),
    [activeSessionId],
  );
  const {
    data: detail,
    loading: detailLoading,
    error: detailError,
    reload: reloadDetail,
  } = useAsyncResource(loadDetail, null);

  const activeSession = detail?.session
    ? {
        session_id: detail.session.session_id,
        title: detail.session.name,
        status: detail.session.status,
        updated_at: detail.session.updated_at,
        summary: detail.runtime?.current_summary ?? '',
      }
    : sessions.find((session) => session.session_id === activeSessionId) ?? null;

  const messages = useMemo(() => {
    const baseMessages = (detail?.messages ?? []).map((message) => ({
      message_id: message.id,
      kind: 'message',
      role: message.role === 'user' ? 'user' : 'agent',
      author: message.role === 'user' ? '你' : message.name || 'Leader Agent',
      content: renderContentBlocks(message.content),
    }));
    return [
      ...baseMessages,
      ...optimisticMessages.filter((message) => message.session_id === activeSessionId),
    ];
  }, [activeSessionId, detail, optimisticMessages]);

  const runtime = detail
    ? {
        session_title: detail.session.name,
        session_status: detail.session.status,
        session_team: detail.team?.name ?? '—',
        session_workspace: detail.workspace_status?.name ?? '—',
        agent_status: detail.session.status,
        task_status: detail.session.status,
        plan_steps: detail.runtime?.current_plan?.steps?.length ?? 0,
        current_summary: detail.runtime?.current_summary ?? '暂无 summary',
        waiting_items: detail.runtime?.waiting_items ?? [],
        agent_statuses: detail.runtime?.agent_statuses ?? [],
      }
    : null;

  async function handleSendMessage(content) {
    if (!activeSessionId) return;
    const optimisticMessage = {
      message_id: `optimistic:${Date.now()}`,
      kind: 'message',
      role: 'user',
      author: '你',
      content,
      session_id: activeSessionId,
    };
    setOptimisticMessages((current) => [...current, optimisticMessage]);
    try {
      await api.sendSessionMessage(activeSessionId, content);
      await Promise.all([reloadSessions(), reloadDetail()]);
    } finally {
      setOptimisticMessages((current) =>
        current.filter((message) => message.message_id !== optimisticMessage.message_id),
      );
    }
  }

  async function handleCreateSession(payload) {
    setCreatePending(true);
    setCreateError('');

    try {
      const created = await api.createSession(payload);
      setSelectedSessionId(created.session_id);
      const nextPayload = await loadSessions();
      setSessionsPayload(nextPayload);
      setIsCreateOpen(false);
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : '创建 session 失败');
    } finally {
      setCreatePending(false);
    }
  }

  async function handleCancelSession() {
    if (!activeSessionId) return;
    setCancelPending(true);
    try {
      await api.cancelSession(activeSessionId);
      await Promise.all([reloadSessions(), reloadDetail()]);
    } finally {
      setCancelPending(false);
    }
  }

  async function handleResolveWaitingItem(waitingId, confirmed) {
    if (!activeSessionId) return;
    setWaitingActionId(waitingId);
    try {
      await api.resolveWaitingItem(activeSessionId, waitingId, confirmed);
      await Promise.all([reloadSessions(), reloadDetail()]);
    } finally {
      setWaitingActionId('');
    }
  }

  useEffect(() => {
    if (!activeSessionId || typeof EventSource === 'undefined') {
      return undefined;
    }

    const eventSource = new EventSource(api.buildSessionStreamUrl(activeSessionId));
    const refresh = () => {
      void reloadSessions();
      void reloadDetail();
    };

    eventSource.addEventListener('session.ready', refresh);
    eventSource.addEventListener('session.event', refresh);

    return () => {
      eventSource.removeEventListener('session.ready', refresh);
      eventSource.removeEventListener('session.event', refresh);
      eventSource.close();
    };
  }, [activeSessionId, reloadDetail, reloadSessions]);

  return (
    <div className="chat-page">
      <SessionList
        sessions={sessions.map((session) => ({
          ...session,
          title: session.name,
          summary: session.status,
          updated_at: session.updated_at,
        }))}
        activeSessionId={activeSessionId}
        teams={teams}
        workspaces={workspaces}
        isCreateOpen={isCreateOpen}
        createPending={createPending}
        createError={createError}
        createDisabled={teamsLoading || workspacesLoading}
        onOpenCreate={() => {
          setCreateError('');
          setIsCreateOpen((current) => !current);
        }}
        onCreateSession={(payload) => {
          void handleCreateSession(payload);
        }}
        onSelectSession={setSelectedSessionId}
      />
      <div className="chat-page-center">
        {sessionsLoading || detailLoading ? (
          detail || activeSession ? (
            <ChatPanel
              session={activeSession}
              messages={messages}
              sending={activeSession?.status === 'running'}
              onSendMessage={handleSendMessage}
            />
          ) : (
          <ChatPanel session={activeSession} messages={[]} sending={true} />
          )
        ) : sessionsError || detailError ? (
          <div className="chat-panel-error">
            <p>{sessionsError || detailError}</p>
            <button type="button" className="session-create-btn" onClick={() => { void reloadSessions(); void reloadDetail(); }}>
              重试
            </button>
          </div>
        ) : (
          <ChatPanel
            session={activeSession}
            messages={messages}
            sending={activeSession?.status === 'running'}
            onSendMessage={handleSendMessage}
          />
        )}
      </div>
      <div className="chat-page-runtime">
        <RuntimePanel
          runtime={runtime}
          onCancelSession={() => {
            void handleCancelSession();
          }}
          onResolveWaitingItem={(waitingId, confirmed) => {
            void handleResolveWaitingItem(waitingId, confirmed);
          }}
          cancelPending={cancelPending}
          waitingActionId={waitingActionId}
        />
      </div>
    </div>
  );
}
