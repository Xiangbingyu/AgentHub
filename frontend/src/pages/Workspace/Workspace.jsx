import { useState } from 'react';
import WorkspaceBrowser from '../../components/WorkspaceBrowser/WorkspaceBrowser';
import WorkspaceDetailPanel from '../../components/WorkspaceDetailPanel/WorkspaceDetailPanel';
import { sourceWorkspaces, resourceDetails } from '../../data/mockWorkspace';
import './Workspace.css';

export default function Workspace() {
  const [selectedResourceId, setSelectedResourceId] = useState(
    sourceWorkspaces[0]?.source_workspace_id ?? '',
  );

  const detail = resourceDetails[selectedResourceId] ?? null;

  return (
    <div className="workspace-page">
      <WorkspaceBrowser
        sourceWorkspaces={sourceWorkspaces}
        selectedResourceId={selectedResourceId}
        onSelectResource={setSelectedResourceId}
      />
      <WorkspaceDetailPanel detail={detail} />
    </div>
  );
}
