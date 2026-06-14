import { Send, Smile, Paperclip, MoreHorizontal } from 'lucide-react';
import './ChatPanel.css';

export default function ChatPanel({ session, messages }) {
  if (!session) {
    return (
      <div className="chat-panel-empty">
        <div className="empty-icon">💬</div>
        <p>选择一个会话开始协作</p>
      </div>
    );
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
          messages.map((message) => (
            <div
              key={message.message_id}
              className={`message-wrapper ${message.role === 'user' ? 'send' : 'receive'}`}
            >
              <div className={`message-avatar ${message.role === 'user' ? 'self' : ''}`}>
                {message.author[0]}
              </div>
              <div className="message-content">
                <div className="message-name">{message.author}</div>
                <div className="message-bubble">{message.content}</div>
              </div>
            </div>
          ))
        )}
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
        <textarea className="chat-textarea" placeholder="发送消息..." />
        <div className="chat-input-actions">
          <button type="button" className="send-btn" disabled>
            <Send size={16} />
            发送
          </button>
        </div>
      </div>
    </div>
  );
}
