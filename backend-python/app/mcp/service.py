from __future__ import annotations

from app.runtime.tools.tool_registry import ToolSpec


def _invoke_mcp_tool(tool: object, runtime, arguments):
    return tool.run(arguments)


class _StaticMcpTool:
    def __init__(self, definition: dict[str, object]) -> None:
        self.definition = definition

    def run(self, arguments):
        return {"arguments": arguments, "definition": self.definition}

class McpService:
    def build_runtime(self, mcp_config: dict[str, object]) -> dict[str, object]:
        if not mcp_config.get("enabled"):
            return {"enabled": False, "tools": []}

        specs: list[ToolSpec] = []
        for server in mcp_config.get("servers", []):
            if not server.get("enabled", True):
                continue
            specs.extend(self.build_tool_specs(server_name=server["name"], tools=server.get("tools", [])))
        return {"enabled": True, "tools": specs}

    def build_tool_specs(self, *, server_name: str, tools: list[dict[str, object]]) -> list[ToolSpec]:
        specs: list[ToolSpec] = []
        for item in tools:
            normalized = str(item["name"]).replace(" ", "_")
            tool_name = f"{server_name}__{normalized}"
            definition = {
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": item.get("description", ""),
                    "parameters": item.get("input_schema", {"type": "object", "properties": {}}),
                },
            }
            specs.append(
                ToolSpec(
                    name=tool_name,
                    tool=_StaticMcpTool(definition),
                    definition=definition,
                    request_model=None,
                    invoke=_invoke_mcp_tool,
                )
            )
        return specs
