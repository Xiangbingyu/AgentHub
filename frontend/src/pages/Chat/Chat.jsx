import { useRef, useState } from 'react';
import SessionList from '../../components/SessionList/SessionList';
import ChatPanel from '../../components/ChatPanel/ChatPanel';
import RuntimePanel from '../../components/RuntimePanel/RuntimePanel';
import { sessions, messagesBySession, runtimeBySession } from '../../data/mockChat';
import './Chat.css';

const RUNTIME_PANEL_DEFAULT_WIDTH = 360;
const RUNTIME_PANEL_MIN_WIDTH = 280;
const RUNTIME_PANEL_MAX_WIDTH = 560;
const CENTER_PANEL_MIN_WIDTH = 480;
const RUNTIME_COLLAPSED_WIDTH = 44;

export default function Chat() {
  const [activeSessionId, setActiveSessionId] = useState(sessions[0]?.session_id ?? '');
  const [runtimeWidth, setRuntimeWidth] = useState(RUNTIME_PANEL_DEFAULT_WIDTH);
  const [runtimeCollapsed, setRuntimeCollapsed] = useState(false);
  const containerRef = useRef(null);

  const activeSession = sessions.find((session) => session.session_id === activeSessionId) ?? null;
  const messages = messagesBySession[activeSessionId] ?? [];
  const runtime = runtimeBySession[activeSessionId] ?? null;

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
        <ChatPanel session={activeSession} messages={messages} />
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
