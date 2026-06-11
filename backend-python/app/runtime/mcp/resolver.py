from __future__ import annotations

from app.mcp.service import McpService


class McpRuntimeResolver:
    def __init__(self, service: McpService | None = None) -> None:
        self.service = service or McpService()

    def resolve(self, mcp_config: dict[str, object]) -> dict[str, object]:
        return self.service.build_runtime(mcp_config)
