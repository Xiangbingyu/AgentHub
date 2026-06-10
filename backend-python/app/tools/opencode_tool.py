from __future__ import annotations

from app.schemas.opencode_tool import OpenCodeToolRequest
from app.tools.external_code_runner import ExternalCodeRunner


class OpenCodeTool:
    def __init__(self, runner: ExternalCodeRunner | None = None) -> None:
        self.runner = runner or ExternalCodeRunner()

    def run(self, *, runtime, arguments: OpenCodeToolRequest | dict, **_kwargs):
        request = arguments if isinstance(arguments, OpenCodeToolRequest) else OpenCodeToolRequest.model_validate(arguments)
        tool_options = _resolve_tool_options(runtime.tool_config, "opencode_tool")
        response = self.runner.run(runtime=runtime, framework="opencode", tool_options=tool_options, prompt=request.prompt)
        return {"status": "ok", "framework": "opencode", "content": response.content, "raw": response.raw}


def _resolve_tool_options(tool_config: dict[str, object], tool_name: str) -> dict[str, object]:
    for item in tool_config.get("tools", []):
        if item.get("name") == tool_name:
            return dict(item.get("options", {}))
    return {}
