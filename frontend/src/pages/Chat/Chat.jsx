import { useCallback, useEffect, useRef, useState } from 'react';
import SessionList from '../../components/SessionList/SessionList';
import ChatPanel from '../../components/ChatPanel/ChatPanel';
import RuntimePanel from '../../components/RuntimePanel/RuntimePanel';
import Modal from '../../components/Modal/Modal';
import useSessionStream from '../../hooks/useSessionStream';
import {
  listSessions,
  getSessionPage,
  postSessionMessage,
  listSourceWorkspaces,
  createSessionFromSource,
} from '../../utils/api';
import './Chat.css';

const RUNTIME_PANEL_DEFAULT_WIDTH = 360;
const RUNTIME_PANEL_MIN_WIDTH = 280;
const RUNTIME_PANEL_MAX_WIDTH = 560;
const CENTER_PANEL_MIN_WIDTH = 480;
const RUNTIME_COLLAPSED_WIDTH = 44;

function roleToAuthor(role) {
  return role === 'user' ? '你' : 'Agent';
}

// 后端 main_timeline 事件 → ChatPanel 消息形状
function eventToMessage(event) {
  const role = event.payload?.role === 'user' ? 'user' : 'agent';
  return {
    message_id: `evt-${event.sequence_no}`,
    sequence_no: event.sequence_no,
    role,
    author: event.payload?.author || roleToAuthor(event.payload?.role),
    content: event.payload?.content ?? '',
  };
}

export default function Chat() {
  const [sessions, setSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState('');
  const [messages, setMessages] = useState([]);
  const [sessionWorkspace, setSessionWorkspace] = useState(null);
  const [sending, setSending] = useState(false);
  const [runtimeWidth, setRuntimeWidth] = useState(RUNTIME_PANEL_DEFAULT_WIDTH);
  const [runtimeCollapsed, setRuntimeCollapsed] = useState(false);
  const containerRef = useRef(null);

  // 建 session 弹窗状态
  const [createOpen, setCreateOpen] = useState(false);
  const [sources, setSources] = useState([]);
  const [newTitle, setNewTitle] = useState('');
  const [newSourceId, setNewSourceId] = useState('');
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState('');

  function refreshSessions(selectId) {
    return listSessions()
      .then((rows) => {
        setSessions(rows);
        if (selectId) {
          setActiveSessionId(selectId);
        } else {
          setActiveSessionId((current) => current || rows[0]?.session_id || '');
        }
        return rows;
      })
      .catch(() => setSessions([]));
  }

  // 应用启动：拉会话列表
  useEffect(() => {
    refreshSessions();
  }, []);

  function openCreateModal() {
    setCreateError('');
    setNewTitle('');
    setCreateOpen(true);
    listSourceWorkspaces()
      .then((rows) => {
        setSources(rows);
        setNewSourceId((current) => current || rows[0]?.source_workspace_id || '');
      })
      .catch(() => setSources([]));
  }

  function handleCreateSession() {
    if (!newSourceId || !newTitle.trim()) {
      setCreateError('请填写标题并选择一个 source workspace');
      return;
    }
    setCreating(true);
    setCreateError('');
    createSessionFromSource({ source_workspace_id: newSourceId, title: newTitle.trim() })
      .then((session) => {
        setCreateOpen(false);
        return refreshSessions(session.session_id);
      })
      .catch((err) => setCreateError(err.message || '创建失败'))
      .finally(() => setCreating(false));
  }

  // 选中 session：拉历史 + workspace 快照
  useEffect(() => {
    if (!activeSessionId) {
      return undefined;
    }
    let cancelled = false;
    getSessionPage(activeSessionId)
      .then((page) => {
        if (cancelled) {
          return;
        }
        const history = (page.main_timeline ?? [])
          .filter((event) => event.event_type === 'session.message.appended')
          .map(eventToMessage);
        setMessages(history);
        setSessionWorkspace(page.session_workspace ?? null);
      })
      .catch(() => {
        if (cancelled) {
          return;
        }
        setMessages([]);
        setSessionWorkspace(null);
      });
    return () => {
      cancelled = true;
    };
  }, [activeSessionId]);

  // SSE 实时：按 sequence_no 去重后追加 main_timeline 消息
  const handleStreamEvent = useCallback((event) => {
    if (event.event_type !== 'session.message.appended') {
      return;
    }
    const incoming = eventToMessage(event);
    setMessages((current) => {
      if (current.some((m) => m.sequence_no === incoming.sequence_no)) {
        return current;
      }
      return [...current, incoming].sort(
        (a, b) => (a.sequence_no ?? 0) - (b.sequence_no ?? 0),
      );
    });
  }, []);

  useSessionStream(activeSessionId, handleStreamEvent);

  function handleSendMessage(content) {
    if (!activeSessionId) {
      return;
    }
    setSending(true);
    postSessionMessage(activeSessionId, content)
      .catch(() => undefined)
      .finally(() => setSending(false));
    // agent 回复经 SSE 回流追加；用户消息也由后端落 main_timeline 事件回流
  }

  const activeSession =
    sessions.find((session) => session.session_id === activeSessionId) ?? null;

  const runtime = activeSession
    ? {
        session_title: activeSession.title,
        session_status: activeSession.status,
        session_workspace: sessionWorkspace?.name ?? '—',
        source_workspace: sessionWorkspace?.source_workspace_id ?? '—',
        agent_status: sending ? 'running' : 'idle',
        task_status: '—',
        plan_steps: 0,
      }
    : null;

  function clampWidth(value, min, max) {
    const safeMax = Math.max(min, max);
    return Math.min(Math.max(value, min), safeMax);
  }

  function startResize(event) {
    event.preventDefault();
    const container = containerRef.current;
    if (!container || runtimeCollapsed) {
      return;
    }
    const rect = container.getBoundingClientRect();

    function handleMouseMove(moveEvent) {
      const nextWidth = clampWidth(
        rect.right - moveEvent.clientX,
        RUNTIME_PANEL_MIN_WIDTH,
        Math.min(RUNTIME_PANEL_MAX_WIDTH, rect.width - CENTER_PANEL_MIN_WIDTH),
      );
      setRuntimeWidth(nextWidth);
    }

    function handleMouseUp() {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
      document.body.classList.remove('is-resizing-panels');
    }

    document.body.classList.add('is-resizing-panels');
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
  }

  return (
    <div className="chat-page" ref={containerRef}>
      <SessionList
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelectSession={setActiveSessionId}
        onCreateSession={openCreateModal}
      />
      <div className="chat-page-center">
        <ChatPanel
          session={activeSession}
          messages={messages}
          onSendMessage={handleSendMessage}
          sending={sending}
        />
      </div>
      <div
        className={`chat-page-runtime ${runtimeCollapsed ? 'collapsed' : ''}`}
        style={{ width: `${runtimeCollapsed ? RUNTIME_COLLAPSED_WIDTH : runtimeWidth}px` }}
      >
        {!runtimeCollapsed ? (
          <button
            type="button"
            className="panel-resize-handle"
            aria-label="调整运行态宽度"
            onMouseDown={startResize}
          />
        ) : null}
        <RuntimePanel
          runtime={runtime}
          collapsed={runtimeCollapsed}
          onToggleCollapse={() => setRuntimeCollapsed((current) => !current)}
        />
      </div>

      <Modal open={createOpen} title="新建 Session" onClose={() => setCreateOpen(false)}>
        {createError ? <div className="modal-error">{createError}</div> : null}
        <div className="modal-field">
          <label htmlFor="new-session-title">会话标题</label>
          <input
            id="new-session-title"
            type="text"
            value={newTitle}
            placeholder="例如：重构登录模块"
            onChange={(event) => setNewTitle(event.target.value)}
          />
        </div>
        <div className="modal-field">
          <label htmlFor="new-session-source">Source Workspace（将自动派生隔离副本）</label>
          <select
            id="new-session-source"
            value={newSourceId}
            onChange={(event) => setNewSourceId(event.target.value)}
          >
            {sources.length === 0 ? <option value="">（暂无，请先在 Workspace 页创建）</option> : null}
            {sources.map((source) => (
              <option key={source.source_workspace_id} value={source.source_workspace_id}>
                {source.name}
              </option>
            ))}
          </select>
        </div>
        <div className="modal-actions">
          <button type="button" className="modal-btn" onClick={() => setCreateOpen(false)}>
            取消
          </button>
          <button
            type="button"
            className="modal-btn primary"
            disabled={creating}
            onClick={handleCreateSession}
          >
            {creating ? '创建中…' : '创建'}
          </button>
        </div>
      </Modal>
    </div>
  );
}
