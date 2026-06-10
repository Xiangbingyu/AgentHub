from __future__ import annotations

from app.schemas.codex_tool import CodexToolRequest
from app.tools.external_code_runner import ExternalCodeRunner


class CodexTool:
    def __init__(self, runner: ExternalCodeRunner | None = None) -> None:
        self.runner = runner or ExternalCodeRunner()

    def run(self, *, runtime, arguments: CodexToolRequest | dict, **_kwargs):
        request = arguments if isinstance(arguments, CodexToolRequest) else CodexToolRequest.model_validate(arguments)
        tool_options = _resolve_tool_options(runtime.tool_config, "codex_tool")
        response = self.runner.run(runtime=runtime, framework="codex", tool_options=tool_options, prompt=request.prompt)
        return {"status": "ok", "framework": "codex", "content": response.content, "raw": response.raw}


def _resolve_tool_options(tool_config: dict[str, object], tool_name: str) -> dict[str, object]:
    for item in tool_config.get("tools", []):
        if item.get("name") == tool_name:
            return dict(item.get("options", {}))
    return {}
