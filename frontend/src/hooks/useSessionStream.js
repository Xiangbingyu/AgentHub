import { useEffect } from 'react';
import { sessionStreamUrl } from '../utils/api';

// 为指定 session 打开 SSE 流，按 event scope 分发。
// onEvent(event) 收到形如 { sequence_no, event_type, payload } 的事件。
// 切换 sessionId 时自动关旧开新；浏览器原生携带 Last-Event-ID 重连。
export default function useSessionStream(sessionId, onEvent) {
  useEffect(() => {
    if (!sessionId) {
      return undefined;
    }

    const source = new EventSource(sessionStreamUrl(sessionId));

    // 后端 SSE 帧带 event: 类型，这里统一监听已知类型 + 默认 message。
    const eventTypes = [
      'run.started',
      'run.completed',
      'session.message.appended',
      'subtask.delegated',
      'subtask.completed',
      'plan.updated',
      'workspace.changed',
      'message',
    ];

    function handle(rawEvent) {
      let payload;
      try {
        payload = rawEvent.data ? JSON.parse(rawEvent.data) : {};
      } catch {
        payload = { raw: rawEvent.data };
      }
      onEvent({
        sequence_no: rawEvent.lastEventId ? Number(rawEvent.lastEventId) : null,
        event_type: rawEvent.type,
        payload,
      });
    }

    eventTypes.forEach((type) => source.addEventListener(type, handle));

    return () => {
      eventTypes.forEach((type) => source.removeEventListener(type, handle));
      source.close();
    };
  }, [sessionId, onEvent]);
}
