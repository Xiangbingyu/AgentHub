from __future__ import annotations

import os
import subprocess

from agent_service.app.llm.llm_types import LlmMessage, LlmRequest
from agent_service.app.schemas.claude_code_tool import ClaudeCodeToolRequest
from agent_service.app.tools.framework_adapters.claude_code_adapter import ClaudeCodeAdapter


class ClaudeCodeTool:
    def run(self, *, runtime, arguments: ClaudeCodeToolRequest | dict, **_kwargs):
        request = arguments if isinstance(arguments, ClaudeCodeToolRequest) else ClaudeCodeToolRequest.model_validate(arguments)
        tool_options = _resolve_tool_options(runtime.tool_config, "claude_code_tool")
        adapter = ClaudeCodeAdapter()
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
        return {"status": "ok", "framework": "claude", "content": response.content, "raw": response.raw}


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
