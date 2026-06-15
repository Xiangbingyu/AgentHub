import { useEffect, useRef, useState } from 'react';
import { Send, Smile, Paperclip, MoreHorizontal } from 'lucide-react';
import './ChatPanel.css';

export default function ChatPanel({ session, messages, onSendMessage, sending }) {
  const [draft, setDraft] = useState('');
  const messageEndRef = useRef(null);

  // 新消息进来时滚动到底部
  useEffect(() => {
    messageEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

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
    if (!content || sending) {
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
        {messages.length === 0 ? (
          <div className="chat-state">还没有消息，开始对话吧。</div>
        ) : (
          messages.map((message) => {
            const isUser = message.role === 'user';
            return (
              <div
                key={message.message_id}
                className={`message-wrapper ${isUser ? 'send' : 'receive'}`}
              >
                <div className={`message-avatar ${isUser ? 'self' : ''}`} aria-hidden="true">
                  {isUser ? '你' : 'AI'}
                </div>
                <div className="message-content">
                  <div className="message-name">{message.author}</div>
                  <div className="message-bubble">
                    {message.content}
                    {message.pending ? <span className="stream-cursor">▋</span> : null}
                  </div>
                </div>
              </div>
            );
          })
        )}
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
            disabled={sending || !draft.trim()}
          >
            <Send size={16} />
            {sending ? '发送中' : '发送'}
          </button>
        </div>
      </div>
    </div>
  );
}
