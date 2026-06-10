from __future__ import annotations

from app.schemas.claude_code_tool import ClaudeCodeToolRequest
from app.tools.external_code_runner import ExternalCodeRunner


class ClaudeCodeTool:
    def __init__(self, runner: ExternalCodeRunner | None = None) -> None:
        self.runner = runner or ExternalCodeRunner()

    def run(self, *, runtime, arguments: ClaudeCodeToolRequest | dict, **_kwargs):
        request = arguments if isinstance(arguments, ClaudeCodeToolRequest) else ClaudeCodeToolRequest.model_validate(arguments)
        tool_options = _resolve_tool_options(runtime.tool_config, "claude_code_tool")
        response = self.runner.run(runtime=runtime, framework="claude", tool_options=tool_options, prompt=request.prompt)
        return {"status": "ok", "framework": "claude", "content": response.content, "raw": response.raw}


def _resolve_tool_options(tool_config: dict[str, object], tool_name: str) -> dict[str, object]:
    for item in tool_config.get("tools", []):
        if item.get("name") == tool_name:
            return dict(item.get("options", {}))
    return {}
