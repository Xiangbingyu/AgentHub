import { useCallback, useEffect, useRef, useState } from 'react';
import SessionList from '../../components/SessionList/SessionList';
import ChatPanel from '../../components/ChatPanel/ChatPanel';
import RuntimePanel from '../../components/RuntimePanel/RuntimePanel';
import useSessionStream from '../../hooks/useSessionStream';
import {
  listSessions,
  getSessionPage,
  postSessionMessage,
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

  // 应用启动：拉会话列表
  useEffect(() => {
    listSessions()
      .then((rows) => {
        setSessions(rows);
        setActiveSessionId((current) => current || rows[0]?.session_id || '');
      })
      .catch(() => setSessions([]));
  }, []);

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
    </div>
  );
}
