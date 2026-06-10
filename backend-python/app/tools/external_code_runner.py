from __future__ import annotations

import os
import subprocess

from app.llm.llm_executor import resolve_framework_adapter
from app.llm.llm_types import LlmMessage, LlmRequest, LlmResponse


class ExternalCodeRunner:
    def run(self, *, runtime, framework: str, tool_options: dict[str, object], prompt: str) -> LlmResponse:
        adapter = resolve_framework_adapter(framework)
        request = LlmRequest(
            system_prompt="",
            context_prompt="",
            messages=[LlmMessage(role="user", content=prompt)],
            tools=[],
            tool_choice=None,
            model=runtime.executor_config.get("model", ""),
        )
        command_args, env = adapter.build_command(
            runtime=runtime,
            request=request,
            env=dict(os.environ),
            options=tool_options,
        )
        completed = subprocess.run(
            command_args,
            cwd=runtime.workspace_root,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=int(tool_options.get("timeout_seconds", 300)),
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError((completed.stderr or completed.stdout or "external code tool failed").strip())
        return adapter.parse_response(completed)
