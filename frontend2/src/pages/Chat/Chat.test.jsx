import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, test, vi } from 'vitest';
import Chat from './Chat';

class MockEventSource {
  static instances = [];

  constructor(url) {
    this.url = url;
    this.listeners = new Map();
    this.closed = false;
    MockEventSource.instances.push(this);
  }

  addEventListener(type, listener) {
    const current = this.listeners.get(type) ?? [];
    current.push(listener);
    this.listeners.set(type, current);
  }

  removeEventListener(type, listener) {
    const current = this.listeners.get(type) ?? [];
    this.listeners.set(
      type,
      current.filter((item) => item !== listener),
    );
  }

  emit(type, data) {
    const event = { data: JSON.stringify(data) };
    for (const listener of this.listeners.get(type) ?? []) {
      listener(event);
    }
  }

  close() {
    this.closed = true;
  }
}

globalThis.EventSource = MockEventSource;

vi.mock('../../utils/api', () => ({
  api: {
    buildSessionStreamUrl: vi.fn((sessionId) => `http://127.0.0.1:8000/api/v1/sessions/${sessionId}/stream`),
    listSessions: vi.fn(),
    getSessionDetail: vi.fn(),
    sendSessionMessage: vi.fn(),
    createSession: vi.fn(),
    cancelSession: vi.fn(),
    resolveWaitingItem: vi.fn(),
    listTeams: vi.fn(),
    listWorkspaces: vi.fn(),
  },
}));

import { api } from '../../utils/api';

describe('Chat', () => {
  beforeEach(() => {
    cleanup();
    MockEventSource.instances = [];
    vi.clearAllMocks();
  });

  test('subscribes to session stream and refreshes detail on session events', async () => {
    api.listSessions.mockResolvedValue({
      sessions: [
        {
          session_id: 'session-1',
          name: 'Existing Session',
          status: 'idle',
          updated_at: '2026-06-17T18:00:00',
        },
      ],
    });
    api.listTeams.mockResolvedValue({ teams: [] });
    api.listWorkspaces.mockResolvedValue({ workspaces: [] });
    api.getSessionDetail
      .mockResolvedValueOnce({
        session: {
          session_id: 'session-1',
          name: 'Existing Session',
          status: 'idle',
          updated_at: '2026-06-17T18:00:00',
        },
        team: { name: 'Default Team' },
        messages: [],
        runtime: {
          current_summary: '',
          current_plan: null,
          waiting_items: [],
          agent_statuses: [],
        },
        workspace_status: { name: 'Project Alpha' },
      })
      .mockResolvedValueOnce({
        session: {
          session_id: 'session-1',
          name: 'Existing Session',
          status: 'running',
          updated_at: '2026-06-17T18:01:00',
        },
        team: { name: 'Default Team' },
        messages: [
          {
            id: 'message-1',
            role: 'assistant',
            name: 'Leader Agent',
            content: [{ type: 'text', text: 'Streamed reply' }],
          },
        ],
        runtime: {
          current_summary: 'updated',
          current_plan: null,
          waiting_items: [],
          agent_statuses: [],
        },
        workspace_status: { name: 'Project Alpha' },
      });

    render(<Chat />);

    await screen.findByRole('heading', { level: 3, name: 'Existing Session' });

    expect(MockEventSource.instances).toHaveLength(1);
    MockEventSource.instances[0].emit('session.event', { type: 'message.created' });

    expect(screen.getByRole('heading', { level: 3, name: 'Existing Session' })).toBeTruthy();
    await waitFor(() => {
      expect(screen.getByText('Streamed reply')).toBeTruthy();
    });
  });

  test('keeps existing history visible while stream refresh is in flight', async () => {
    let resolveDetail;
    api.listSessions.mockResolvedValue({
      sessions: [
        {
          session_id: 'session-1',
          name: 'Existing Session',
          status: 'idle',
          updated_at: '2026-06-17T18:00:00',
        },
      ],
    });
    api.listTeams.mockResolvedValue({ teams: [] });
    api.listWorkspaces.mockResolvedValue({ workspaces: [] });
    api.getSessionDetail
      .mockResolvedValueOnce({
        session: {
          session_id: 'session-1',
          name: 'Existing Session',
          status: 'idle',
          updated_at: '2026-06-17T18:00:00',
        },
        team: { name: 'Default Team' },
        messages: [
          {
            id: 'message-1',
            role: 'assistant',
            name: 'Leader Agent',
            content: [{ type: 'text', text: 'Old history' }],
          },
        ],
        runtime: {
          current_summary: '',
          current_plan: null,
          waiting_items: [],
          agent_statuses: [],
        },
        workspace_status: { name: 'Project Alpha' },
      })
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveDetail = resolve;
          }),
      );

    render(<Chat />);

    await screen.findByText('Old history');
    MockEventSource.instances[0].emit('session.event', { type: 'message.created' });

    expect(screen.getByText('Old history')).toBeTruthy();

    resolveDetail({
      session: {
        session_id: 'session-1',
        name: 'Existing Session',
        status: 'running',
        updated_at: '2026-06-17T18:01:00',
      },
      team: { name: 'Default Team' },
      messages: [
        {
          id: 'message-1',
          role: 'assistant',
          name: 'Leader Agent',
          content: [{ type: 'text', text: 'Old history' }],
        },
        {
          id: 'message-2',
          role: 'assistant',
          name: 'Leader Agent',
          content: [{ type: 'text', text: 'New history' }],
        },
      ],
      runtime: {
        current_summary: 'updated',
        current_plan: null,
        waiting_items: [],
        agent_statuses: [],
      },
      workspace_status: { name: 'Project Alpha' },
    });

    await waitFor(() => {
      expect(screen.getByText('New history')).toBeTruthy();
    });
  });

  test('creates a session and switches to it', async () => {
    api.listSessions
      .mockResolvedValueOnce({ sessions: [] })
      .mockResolvedValueOnce({
        sessions: [
          {
            session_id: 'session-1',
            name: 'New Session',
            status: 'idle',
            updated_at: '2026-06-17T18:00:00',
          },
        ],
      });
    api.listTeams.mockResolvedValue({
      teams: [
        {
          team_id: 'team-1',
          name: 'Default Team',
        },
      ],
    });
    api.listWorkspaces.mockResolvedValue({
      workspaces: [
        {
          workspace_id: 'workspace-1',
          name: 'Project Alpha',
        },
      ],
    });
    api.createSession.mockResolvedValue({
      session_id: 'session-1',
      name: 'New Session',
      status: 'idle',
      updated_at: '2026-06-17T18:00:00',
    });
    api.getSessionDetail.mockResolvedValue({
      session: {
        session_id: 'session-1',
        name: 'New Session',
        status: 'idle',
        updated_at: '2026-06-17T18:00:00',
      },
      team: { name: 'Default Team' },
      messages: [],
      runtime: {
        current_summary: '',
        current_plan: null,
        waiting_items: [],
        agent_statuses: [],
      },
      workspace_status: {
        name: 'Project Alpha',
      },
    });

    const user = userEvent.setup();
    render(<Chat />);

    await screen.findByText('暂无会话');

    await user.click(screen.getAllByRole('button', { name: '新建' })[0]);
    await screen.findByRole('option', { name: 'Project Alpha' });
    await screen.findByRole('option', { name: 'Default Team' });
    await user.type(screen.getByLabelText('Session 名称'), 'New Session');
    await user.selectOptions(screen.getByLabelText('绑定 Workspace'), 'workspace-1');
    await user.selectOptions(screen.getByLabelText('绑定 Team'), 'team-1');
    await user.click(screen.getByRole('button', { name: '创建 session' }));

    await waitFor(() => {
      expect(api.createSession).toHaveBeenCalledWith({
        name: 'New Session',
        workspace_id: 'workspace-1',
        team_id: 'team-1',
      });
    });

    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 3, name: 'New Session' })).toBeTruthy();
    });
  });

  test('resolves waiting items and cancels from runtime panel', async () => {
    api.listSessions.mockResolvedValue({
      sessions: [
        {
          session_id: 'session-1',
          name: 'Existing Session',
          status: 'waiting',
          updated_at: '2026-06-17T18:00:00',
        },
      ],
    });
    api.listTeams.mockResolvedValue({ teams: [] });
    api.listWorkspaces.mockResolvedValue({ workspaces: [] });
    api.getSessionDetail.mockResolvedValue({
      session: {
        session_id: 'session-1',
        name: 'Existing Session',
        status: 'waiting',
        updated_at: '2026-06-17T18:00:00',
      },
      team: { name: 'Default Team' },
      messages: [],
      runtime: {
        current_summary: '',
        current_plan: null,
        waiting_items: [
          {
            waiting_id: 'wait-1',
            title: 'Confirm tool call: Write',
            status: 'pending',
            message: 'Tool Write requires confirmation.',
          },
        ],
        agent_statuses: [],
      },
      workspace_status: { name: 'Project Alpha' },
    });
    api.resolveWaitingItem.mockResolvedValue({ status: 'resolved' });
    api.cancelSession.mockResolvedValue({ status: 'cancelling' });

    const user = userEvent.setup();
    render(<Chat />);

    await screen.findByText('Tool Write requires confirmation.');

    await user.click(screen.getByRole('button', { name: '批准 wait-1' }));
    await waitFor(() => {
      expect(api.resolveWaitingItem).toHaveBeenCalledWith('session-1', 'wait-1', true);
    });

    await user.click(screen.getAllByRole('button', { name: '取消当前运行' })[0]);
    await waitFor(() => {
      expect(api.cancelSession).toHaveBeenCalledWith('session-1');
    });
  });

  test('shows the user message immediately before background refresh completes', async () => {
    let resolveSend;
    api.listSessions.mockResolvedValue({
      sessions: [
        {
          session_id: 'session-1',
          name: 'Existing Session',
          status: 'idle',
          updated_at: '2026-06-17T18:00:00',
        },
      ],
    });
    api.listTeams.mockResolvedValue({ teams: [] });
    api.listWorkspaces.mockResolvedValue({ workspaces: [] });
    api.getSessionDetail.mockResolvedValue({
      session: {
        session_id: 'session-1',
        name: 'Existing Session',
        status: 'idle',
        updated_at: '2026-06-17T18:00:00',
      },
      team: { name: 'Default Team' },
      messages: [
        {
          id: 'message-1',
          role: 'assistant',
          name: 'Leader Agent',
          content: [{ type: 'text', text: 'Old history' }],
        },
      ],
      runtime: {
        current_summary: '',
        current_plan: null,
        waiting_items: [],
        agent_statuses: [],
      },
      workspace_status: { name: 'Project Alpha' },
    });
    api.sendSessionMessage.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveSend = resolve;
        }),
    );

    const user = userEvent.setup();
    render(<Chat />);

    await screen.findByText('Old history');
    await user.type(screen.getByPlaceholderText('发送消息...'), 'hello world');
    await user.click(screen.getByRole('button', { name: '发送' }));

    expect(screen.getByText('hello world')).toBeTruthy();
    expect(screen.getByText('Old history')).toBeTruthy();

    resolveSend({ status: 'accepted' });

    await waitFor(() => {
      expect(api.sendSessionMessage).toHaveBeenCalledWith('session-1', 'hello world');
    });
  });
});
