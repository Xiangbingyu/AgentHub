import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, test, vi } from 'vitest';
import Workspace from './Workspace';

vi.mock('../../utils/api', () => ({
  api: {
    listWorkspaces: vi.fn(),
    createWorkspace: vi.fn(),
    getWorkspaceTree: vi.fn(),
    getWorkspaceFile: vi.fn(),
  },
}));

import { api } from '../../utils/api';

describe('Workspace', () => {
  test('creates a workspace, reloads list, and shows the new workspace detail', async () => {
    api.listWorkspaces
      .mockResolvedValueOnce({
        workspaces: [
          {
            workspace_id: 'workspace-1',
            name: 'Existing Workspace',
            root_path: '/tmp/existing',
            status: 'ready',
          },
        ],
      })
      .mockResolvedValueOnce({
        workspaces: [
          {
            workspace_id: 'workspace-1',
            name: 'Existing Workspace',
            root_path: '/tmp/existing',
            status: 'ready',
          },
          {
            workspace_id: 'workspace-2',
            name: 'New Workspace',
            root_path: '/tmp/new',
            status: 'ready',
          },
        ],
      });
    api.createWorkspace.mockResolvedValue({
      workspace_id: 'workspace-2',
      name: 'New Workspace',
      root_path: '/tmp/new',
      status: 'ready',
    });
    api.getWorkspaceTree.mockResolvedValue({ entries: [] });

    const user = userEvent.setup();
    render(<Workspace />);

    await screen.findByRole('heading', { level: 3, name: 'Existing Workspace' });

    await user.click(screen.getByRole('button', { name: '新建' }));
    await user.type(screen.getByLabelText('Workspace 名称'), 'New Workspace');
    await user.type(screen.getByLabelText('Workspace 描述'), 'Created from UI');
    await user.click(screen.getByRole('button', { name: '创建 workspace' }));

    await waitFor(() => {
      expect(api.createWorkspace).toHaveBeenCalledWith({
        name: 'New Workspace',
        description: 'Created from UI',
      });
    });

    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 3, name: 'New Workspace' })).toBeTruthy();
    });
  });
});
