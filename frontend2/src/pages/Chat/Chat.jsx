import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useAsyncResource } from '../../hooks/useAsyncResource';
import { api } from '../../utils/api';
import ChatPanel from '../../components/ChatPanel/ChatPanel';
import { renderContentBlocks } from '../../utils/message';
import RuntimePanel from '../../components/RuntimePanel/RuntimePanel';
import SessionList from '../../components/SessionList/SessionList';
import PrimaryButton from '../../components/ui/PrimaryButton';
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
  const [streamingMessages, setStreamingMessages] = useState({});
  const [runtimePatch, setRuntimePatch] = useState(null);
  const activeSessionId = selectedSessionId || sessions[0]?.session_id || '';
  const hasDetailRef = useRef(false);

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
        status: runtimePatch?.session_status ?? detail.session.status,
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
    const persistedUserContents = new Set(
      baseMessages.filter((message) => message.role === 'user').map((message) => message.content),
    );
    const persistedIds = new Set(baseMessages.map((message) => message.message_id));
    const liveAssistantMessages = Object.values(streamingMessages).filter(
      (message) => message.session_id === activeSessionId && !persistedIds.has(message.message_id),
    );
    return [
      ...baseMessages,
      ...optimisticMessages.filter(
        (message) =>
          message.session_id === activeSessionId && !persistedUserContents.has(message.content),
      ),
      ...liveAssistantMessages,
    ];
  }, [activeSessionId, detail, optimisticMessages, streamingMessages]);

  const runtime = detail
    ? {
        session_title: detail.session.name,
        session_status: runtimePatch?.session_status ?? detail.session.status,
        session_team: detail.team?.name ?? '—',
        session_workspace: detail.workspace_status?.name ?? '—',
        agent_status: runtimePatch?.session_status ?? detail.session.status,
        task_status: runtimePatch?.session_status ?? detail.session.status,
        plan_steps: detail.runtime?.current_plan?.steps?.length ?? 0,
        current_summary: runtimePatch?.current_summary ?? detail.runtime?.current_summary ?? '暂无 summary',
        waiting_items: runtimePatch?.waiting_items ?? detail.runtime?.waiting_items ?? [],
        agent_statuses: runtimePatch?.agent_statuses ?? detail.runtime?.agent_statuses ?? [],
      }
    : null;

  useEffect(() => {
    hasDetailRef.current = Boolean(detail);
  }, [detail]);

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
      void reloadSessions();
      void reloadDetail();
    } catch (error) {
      setOptimisticMessages((current) =>
        current.filter((message) => message.message_id !== optimisticMessage.message_id),
      );
      throw error;
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
      setRuntimePatch((current) => ({
        ...current,
        session_status: 'idle',
        waiting_items: [],
      }));
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
    const reconcileSnapshot = () => {
      void reloadSessions();
      void reloadDetail();
    };

    const upsertStreamingMessage = (messageId, patch) => {
      setStreamingMessages((current) => ({
        ...current,
        [messageId]: {
          ...current[messageId],
          session_id: activeSessionId,
          ...patch,
        },
      }));
    };

    const handleSessionReady = () => {
      if (!hasDetailRef.current) {
        reconcileSnapshot();
      }
    };

    const handleSessionEvent = (rawEvent) => {
      let payload;
      try {
        payload = JSON.parse(rawEvent.data);
      } catch {
        reconcileSnapshot();
        return;
      }

      if (!payload?.type) {
        reconcileSnapshot();
        return;
      }

      if (payload.type === 'REPLY_START') {
        upsertStreamingMessage(payload.reply_id, {
          message_id: payload.reply_id,
          kind: 'message',
          role: 'agent',
          author: payload.name || 'Leader Agent',
          content: '',
          streaming: true,
        });
        setRuntimePatch((current) => ({
          ...current,
          session_status: 'running',
        }));
        return;
      }

      if (payload.type === 'TEXT_BLOCK_DELTA') {
        setStreamingMessages((current) => ({
          ...current,
          [payload.reply_id]: {
            ...current[payload.reply_id],
            session_id: activeSessionId,
            message_id: payload.reply_id,
            kind: 'message',
            role: 'agent',
            author: current[payload.reply_id]?.author || 'Leader Agent',
            content: `${current[payload.reply_id]?.content || ''}${payload.delta || ''}`,
            streaming: true,
          },
        }));
        return;
      }

      if (payload.type === 'REPLY_END') {
        setStreamingMessages((current) => ({
          ...current,
          [payload.reply_id]: {
            ...current[payload.reply_id],
            streaming: false,
          },
        }));
        setRuntimePatch((current) => ({
          ...current,
          session_status: 'idle',
        }));
        reconcileSnapshot();
        return;
      }

      if (payload.type === 'REQUIRE_USER_CONFIRM' || payload.type === 'REQUIRE_EXTERNAL_EXECUTION') {
        const waitingItems = (payload.tool_calls ?? []).map((toolCall) => ({
          waiting_id: toolCall.id,
          title:
            payload.type === 'REQUIRE_USER_CONFIRM'
              ? `Confirm tool call: ${toolCall.name}`
              : `Await external result: ${toolCall.name}`,
          status: 'pending',
          message:
            payload.type === 'REQUIRE_USER_CONFIRM'
              ? `Tool ${toolCall.name} requires confirmation.`
              : `Tool ${toolCall.name} is waiting for external execution result.`,
        }));
        setRuntimePatch((current) => ({
          ...current,
          session_status: 'waiting',
          waiting_items: waitingItems,
        }));
        return;
      }

      if (payload.type === 'HINT_BLOCK') {
        reconcileSnapshot();
        return;
      }

      reconcileSnapshot();
    };

    eventSource.addEventListener('session.ready', handleSessionReady);
    eventSource.addEventListener('session.event', handleSessionEvent);

    return () => {
      eventSource.removeEventListener('session.ready', handleSessionReady);
      eventSource.removeEventListener('session.event', handleSessionEvent);
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
              onCancelSession={() => {
                void handleCancelSession();
              }}
              cancelPending={cancelPending}
            />
          ) : (
          <ChatPanel session={activeSession} messages={[]} sending={true} />
          )
        ) : sessionsError || detailError ? (
          <div className="chat-panel-error">
            <p>{sessionsError || detailError}</p>
            <PrimaryButton onClick={() => { void reloadSessions(); void reloadDetail(); }}>
              重试
            </PrimaryButton>
          </div>
        ) : (
          <ChatPanel
            session={activeSession}
            messages={messages}
            sending={activeSession?.status === 'running'}
            onSendMessage={handleSendMessage}
            onCancelSession={() => {
              void handleCancelSession();
            }}
            cancelPending={cancelPending}
          />
        )}
      </div>
      <div className="chat-page-runtime">
        <RuntimePanel
          runtime={runtime}
          onResolveWaitingItem={(waitingId, confirmed) => {
            void handleResolveWaitingItem(waitingId, confirmed);
          }}
          waitingActionId={waitingActionId}
        />
      </div>
    </div>
  );
}
