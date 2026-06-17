import { act, cleanup, render, screen, waitFor, within } from '@testing-library/react';
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

  test('streams assistant replies into the active chat without clearing existing history', async () => {
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

    render(<Chat />);

    await screen.findByRole('heading', { level: 3, name: 'Existing Session' });
    expect(screen.getByText('Old history')).toBeTruthy();

    expect(MockEventSource.instances.length).toBeGreaterThanOrEqual(1);
    act(() => {
      MockEventSource.instances.at(-1).emit('session.event', {
        type: 'REPLY_START',
        session_id: 'session-1',
        reply_id: 'reply-1',
        name: 'Leader Agent',
        role: 'assistant',
      });
      MockEventSource.instances.at(-1).emit('session.event', {
        type: 'TEXT_BLOCK_DELTA',
        reply_id: 'reply-1',
        block_id: 'block-1',
        delta: 'Streamed reply',
      });
      MockEventSource.instances.at(-1).emit('session.event', {
        type: 'REPLY_END',
        session_id: 'session-1',
        reply_id: 'reply-1',
      });
    });

    await waitFor(() => {
      expect(screen.getByText('Streamed reply')).toBeTruthy();
    });
    expect(screen.getByText('Old history')).toBeTruthy();
    expect(document.querySelector('.typing-bubble')).toBeNull();
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
        status: 'idle',
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
    await screen.findByRole('heading', { level: 3, name: 'Existing Session' });

    act(() => {
      MockEventSource.instances.at(-1).emit('session.event', {
        type: 'REQUIRE_USER_CONFIRM',
        reply_id: 'reply-1',
        tool_calls: [{ id: 'wait-1', name: 'Write' }],
      });
    });

    await screen.findByText('Tool Write requires confirmation.');

    await user.click(screen.getByRole('button', { name: '批准 wait-1' }));
    await waitFor(() => {
      expect(api.resolveWaitingItem).toHaveBeenCalledWith('session-1', 'wait-1', true);
    });

    act(() => {
      MockEventSource.instances.at(-1).emit('session.event', {
        type: 'REPLY_START',
        session_id: 'session-1',
        reply_id: 'reply-cancel',
        name: 'Leader Agent',
        role: 'assistant',
      });
    });

    await user.click(screen.getByRole('button', { name: '取消当前运行' }));
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

  test('updates runtime panel from incremental runtime events', async () => {
    api.listSessions.mockResolvedValue({
      sessions: [{ session_id: 'session-1', name: 'Existing Session', status: 'idle', updated_at: '2026-06-17T18:00:00' }],
    });
    api.listTeams.mockResolvedValue({ teams: [] });
    api.listWorkspaces.mockResolvedValue({ workspaces: [] });
    api.getSessionDetail.mockResolvedValue({
      session: { session_id: 'session-1', name: 'Existing Session', status: 'idle', updated_at: '2026-06-17T18:00:00' },
      team: { name: 'Default Team' },
      messages: [],
      runtime: { current_summary: '', current_plan: null, waiting_items: [], agent_statuses: [] },
      workspace_status: { name: 'Project Alpha' },
    });

    render(<Chat />);
    await screen.findByText('状态：idle');

    act(() => {
      MockEventSource.instances.at(-1).emit('session.event', {
        type: 'REPLY_START',
        session_id: 'session-1',
        reply_id: 'reply-runtime',
        name: 'Leader Agent',
        role: 'assistant',
      });
    });

    await waitFor(() => {
      const sessionSection = screen.getByText('Session').closest('section');
      expect(within(sessionSection).getByText('状态：running', { selector: 'p' })).toBeTruthy();
    });
  });

  test('shows cancel in the input area while a reply is running', async () => {
    api.listSessions.mockResolvedValue({
      sessions: [{ session_id: 'session-1', name: 'Existing Session', status: 'idle', updated_at: '2026-06-17T18:00:00' }],
    });
    api.listTeams.mockResolvedValue({ teams: [] });
    api.listWorkspaces.mockResolvedValue({ workspaces: [] });
    api.getSessionDetail.mockResolvedValue({
      session: { session_id: 'session-1', name: 'Existing Session', status: 'idle', updated_at: '2026-06-17T18:00:00' },
      team: { name: 'Default Team' },
      messages: [],
      runtime: { current_summary: '', current_plan: null, waiting_items: [], agent_statuses: [] },
      workspace_status: { name: 'Project Alpha' },
    });

    render(<Chat />);
    await screen.findByRole('heading', { level: 3, name: 'Existing Session' });

    act(() => {
      MockEventSource.instances.at(-1).emit('session.event', {
        type: 'REPLY_START',
        session_id: 'session-1',
        reply_id: 'reply-running',
        name: 'Leader Agent',
        role: 'assistant',
      });
    });

    expect(screen.getByRole('button', { name: '取消当前运行' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: '发送' })).toBeNull();
  });

  test('does not keep a stale stream overlay after cancel', async () => {
    api.listSessions.mockResolvedValue({
      sessions: [{ session_id: 'session-1', name: 'Existing Session', status: 'idle', updated_at: '2026-06-17T18:00:00' }],
    });
    api.listTeams.mockResolvedValue({ teams: [] });
    api.listWorkspaces.mockResolvedValue({ workspaces: [] });
    api.getSessionDetail.mockImplementation(() =>
      Promise.resolve({
        session: { session_id: 'session-1', name: 'Existing Session', status: 'idle', updated_at: '2026-06-17T18:00:00' },
        team: { name: 'Default Team' },
        messages: [],
        runtime: { current_summary: '', current_plan: null, waiting_items: [], agent_statuses: [] },
        workspace_status: { name: 'Project Alpha' },
      }),
    );
    api.cancelSession.mockResolvedValue({ status: 'cancelling' });

    const user = userEvent.setup();
    render(<Chat />);
    await screen.findByRole('heading', { level: 3, name: 'Existing Session' });

    act(() => {
      MockEventSource.instances.at(-1).emit('session.event', {
        type: 'REPLY_START',
        session_id: 'session-1',
        reply_id: 'reply-cancel',
        name: 'Leader Agent',
        role: 'assistant',
      });
      MockEventSource.instances.at(-1).emit('session.event', {
        type: 'TEXT_BLOCK_DELTA',
        reply_id: 'reply-cancel',
        block_id: 'block-cancel',
        delta: 'Half way',
      });
    });

    expect(screen.getByText('Half way', { selector: '.message-bubble' })).toBeTruthy();

    await user.click(screen.getByRole('button', { name: '取消当前运行' }));
    await waitFor(() => {
      expect(api.cancelSession).toHaveBeenCalledWith('session-1');
    });

    await waitFor(() => {
      expect(document.querySelector('.typing-bubble')).toBeNull();
    });
  });

  test('keeps optimistic user bubble visible until the real user message arrives', async () => {
    let sendResolved = false;
    api.listSessions.mockResolvedValue({
      sessions: [{ session_id: 'session-1', name: 'Existing Session', status: 'idle', updated_at: '2026-06-17T18:00:00' }],
    });
    api.listTeams.mockResolvedValue({ teams: [] });
    api.listWorkspaces.mockResolvedValue({ workspaces: [] });
    api.getSessionDetail.mockImplementation(() =>
      Promise.resolve({
        session: { session_id: 'session-1', name: 'Existing Session', status: 'idle', updated_at: '2026-06-17T18:00:00' },
        team: { name: 'Default Team' },
        messages: sendResolved
          ? [
              {
                id: 'message-real-user',
                role: 'user',
                name: 'user',
                content: [{ type: 'text', text: 'hello world' }],
              },
            ]
          : [],
        runtime: { current_summary: '', current_plan: null, waiting_items: [], agent_statuses: [] },
        workspace_status: { name: 'Project Alpha' },
      }),
    );
    api.sendSessionMessage.mockImplementation(
      () =>
        new Promise((resolve) => {
          setTimeout(() => {
            sendResolved = true;
            resolve({ status: 'accepted' });
          }, 50);
        }),
    );

    const user = userEvent.setup();
    render(<Chat />);

    await screen.findByRole('heading', { level: 3, name: 'Existing Session' });
    await user.type(screen.getByPlaceholderText('发送消息...'), 'hello world');
    await user.click(screen.getByRole('button', { name: '发送' }));

    expect(screen.getByText('hello world', { selector: '.message-bubble' })).toBeTruthy();

    await waitFor(() => {
      expect(screen.getByText('hello world', { selector: '.message-bubble' })).toBeTruthy();
    });
  });
});
