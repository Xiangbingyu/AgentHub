from __future__ import annotations

import os
import subprocess

from app.llm.llm_types import LlmMessage, LlmRequest
from app.schemas.opencode_tool import OpenCodeToolRequest
from app.tools.framework_adapters.opencode_adapter import OpenCodeAdapter


class OpenCodeTool:
    def run(self, *, runtime, arguments: OpenCodeToolRequest | dict, **_kwargs):
        request = arguments if isinstance(arguments, OpenCodeToolRequest) else OpenCodeToolRequest.model_validate(arguments)
        tool_options = _resolve_tool_options(runtime.tool_config, "opencode_tool")
        adapter = OpenCodeAdapter()
        llm_request = LlmRequest(
            system_prompt="",
            context_prompt="",
            messages=[LlmMessage(role="user", content=request.prompt)],
            tools=[],
            tool_choice=None,
            model=runtime.executor_config.get("model", ""),
        )
        command_args, env = adapter.build_command(
            runtime=runtime,
            request=llm_request,
            env=dict(os.environ),
            options=tool_options,
        )
        completed = subprocess.run(
            command_args,
            cwd=runtime.workspace_root,
            env=env,
            capture_output=True,
            timeout=int(tool_options.get("timeout_seconds", 300)),
            check=False,
        )
        completed = _normalize_completed_output(completed)
        if completed.returncode != 0:
            raise RuntimeError((completed.stderr or completed.stdout or "external code tool failed").strip())
        response = adapter.parse_response(completed)
        return {"status": "ok", "framework": "opencode", "content": response.content, "raw": response.raw}


def _resolve_tool_options(tool_config: dict[str, object], tool_name: str) -> dict[str, object]:
    for item in tool_config.get("tools", []):
        if item.get("name") == tool_name:
            return dict(item.get("options", {}))
    return {}


def _normalize_completed_output(completed):
    stdout = completed.stdout.decode("utf-8", "replace") if isinstance(completed.stdout, bytes) else completed.stdout
    stderr = completed.stderr.decode("utf-8", "replace") if isinstance(completed.stderr, bytes) else completed.stderr
    completed.stdout = stdout
    completed.stderr = stderr
    return completed
