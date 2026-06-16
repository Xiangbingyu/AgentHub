from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RuntimeAssembly:
    session_id: str
    runtime_agent_id: str
    workspace_id: str
