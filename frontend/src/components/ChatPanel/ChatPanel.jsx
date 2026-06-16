import { useEffect, useRef, useState } from 'react';
import { Send, Smile, Paperclip, MoreHorizontal, Wrench, ClipboardList } from 'lucide-react';
import './ChatPanel.css';

const PLAN_STATUS_MARK = {
  completed: '☑',
  in_progress: '▣',
  cancelled: '☒',
  pending: '☐',
};

function StepCard({ icon, title, children }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="timeline-step">
      <button type="button" className="timeline-step-head" onClick={() => setOpen((v) => !v)}>
        <span className="timeline-step-icon">{icon}</span>
        <span className="timeline-step-title">{title}</span>
        <span className="timeline-step-toggle">{open ? '收起' : '详情'}</span>
      </button>
      {open ? <div className="timeline-step-body">{children}</div> : null}
    </div>
  );
}

function formatDetail(value) {
  if (value == null) return '';
  if (typeof value === 'string') return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function renderTimelineItem(item) {
  if (item.kind === 'tool_call') {
    return (
      <div key={item.message_id} className="timeline-row">
        <StepCard icon={<Wrench size={14} />} title={`调用工具 ${item.tool_name}`}>
          <pre className="timeline-pre">{formatDetail(item.arguments)}</pre>
        </StepCard>
      </div>
    );
  }
  if (item.kind === 'tool_result') {
    return (
      <div key={item.message_id} className="timeline-row">
        <StepCard icon={<Wrench size={14} />} title={`工具结果 ${item.tool_name}`}>
          <pre className="timeline-pre">{formatDetail(item.result)}</pre>
        </StepCard>
      </div>
    );
  }
  if (item.kind === 'plan') {
    return (
      <div key={item.message_id} className="timeline-row">
        <div className="plan-card">
          <div className="plan-card-head">
            <ClipboardList size={15} />
            <span className="plan-card-title">{item.title || '执行计划'}</span>
            {item.status ? <span className="plan-card-status">{item.status}</span> : null}
          </div>
          {item.goal ? <div className="plan-card-goal">{item.goal}</div> : null}
          <ul className="plan-card-steps">
            {(item.steps ?? []).map((step, idx) => (
              <li key={step.step_id || idx} className={`plan-step plan-step-${step.status || 'pending'}`}>
                <span className="plan-step-mark">{PLAN_STATUS_MARK[step.status] || '☐'}</span>
                <span className="plan-step-text">{step.content || ''}</span>
              </li>
            ))}
          </ul>
          {item.file_path ? <div className="plan-card-file">{item.file_path}</div> : null}
        </div>
      </div>
    );
  }

  // kind === 'message'
  const isUser = item.role === 'user';
  return (
    <div key={item.message_id} className={`message-wrapper ${isUser ? 'send' : 'receive'}`}>
      <div className={`message-avatar ${isUser ? 'self' : ''}`} aria-hidden="true">
        {isUser ? '你' : 'AI'}
      </div>
      <div className="message-content">
        <div className="message-name">{item.author}</div>
        <div className="message-bubble">{item.content}</div>
      </div>
    </div>
  );
}

export default function ChatPanel({ session, messages, onSendMessage, sending, agentTyping }) {
  const [draft, setDraft] = useState('');
  const messageEndRef = useRef(null);

  // 新消息进来时滚动到底部
  useEffect(() => {
    messageEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, agentTyping]);

  if (!session) {
    return (
      <div className="chat-panel-empty">
        <div className="empty-icon">💬</div>
        <p>选择一个会话开始协作</p>
      </div>
    );
  }

  function handleSend() {
    const content = draft.trim();
    if (!content) {
      return;
    }
    onSendMessage?.(content);
    setDraft('');
  }

  function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSend();
    }
  }

  return (
    <div className="chat-panel">
      <div className="chat-header">
        <div className="header-left">
          <h3>{session.title}</h3>
          <span className="chat-status-tag">{session.status}</span>
        </div>
        <div className="header-right">
          <button type="button" className="icon-btn">
            <MoreHorizontal size={20} />
          </button>
        </div>
      </div>

      <div className="chat-messages">
        {messages.length === 0 && !agentTyping ? (
          <div className="chat-state">还没有消息，开始对话吧。</div>
        ) : (
          messages.map((message) => renderTimelineItem(message))
        )}
        {agentTyping ? (
          <div className="message-wrapper receive">
            <div className="message-avatar" aria-hidden="true">
              AI
            </div>
            <div className="message-content">
              <div className="message-name">Agent</div>
              <div className="message-bubble typing-bubble" aria-label="对方正在输入">
                <span className="typing-dot" />
                <span className="typing-dot" />
                <span className="typing-dot" />
              </div>
            </div>
          </div>
        ) : null}
        <div ref={messageEndRef} />
      </div>

      <div className="chat-input-area">
        <div className="chat-toolbar">
          <button type="button" className="toolbar-btn" title="表情">
            <Smile size={20} />
          </button>
          <button type="button" className="toolbar-btn" title="附件">
            <Paperclip size={20} />
          </button>
        </div>
        <textarea
          className="chat-textarea"
          placeholder="发送消息..."
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={handleKeyDown}
        />
        <div className="chat-input-actions">
          <button
            type="button"
            className="send-btn"
            onClick={handleSend}
            disabled={!draft.trim()}
          >
            <Send size={16} />
            {sending ? '继续发送' : '发送'}
          </button>
        </div>
      </div>
    </div>
  );
}
