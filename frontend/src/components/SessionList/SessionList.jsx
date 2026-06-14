import { useState } from 'react';
import { Plus, Search } from 'lucide-react';
import './SessionList.css';

function formatSessionTime(value) {
  if (!value) {
    return '';
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '';
  }

  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export default function SessionList({ sessions, activeSessionId, onSelectSession, onCreateSession }) {
  const [keyword, setKeyword] = useState('');

  const filteredSessions = sessions.filter((session) => {
    if (!keyword.trim()) {
      return true;
    }
    return session.title.toLowerCase().includes(keyword.trim().toLowerCase());
  });

  return (
    <div className="session-list-container">
      <div className="session-header">
        <div className="header-top">
          <h2>Sessions</h2>
          <button type="button" className="session-create-btn" onClick={() => onCreateSession?.()}>
            <Plus size={16} />
            新建 Session
          </button>
        </div>

        <div className="search-bar">
          <Search size={16} className="search-icon" />
          <input
            type="text"
            placeholder="搜索会话"
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
          />
        </div>
      </div>

      <div className="session-list">
        {filteredSessions.length === 0 ? (
          <div className="session-state">没有匹配的会话</div>
        ) : (
          filteredSessions.map((session) => (
            <div
              key={session.session_id}
              className={`session-item ${activeSessionId === session.session_id ? 'active' : ''}`}
              onClick={() => onSelectSession(session.session_id)}
            >
              <div className="avatar">{session.title[0]}</div>
              <div className="info">
                <div className="info-top">
                  <span className="name">{session.title}</span>
                  <span className="time">{formatSessionTime(session.last_active_at)}</span>
                </div>
                <div className="info-bottom">{session.summary}</div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
