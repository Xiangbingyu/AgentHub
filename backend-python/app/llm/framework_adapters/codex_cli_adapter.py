from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import TYPE_CHECKING

from app.llm.llm_types import LlmRequest, LlmResponse

if TYPE_CHECKING:
    from app.runtime.runtime_assembler import RuntimeBundle


class CodexCliAdapter:
    framework_name = "codex"

    def build_command(
        self,
        runtime: RuntimeBundle,
        request: LlmRequest,
        env: dict[str, str],
        options: dict[str, object] | None = None,
    ) -> tuple[list[str], dict[str, str]]:
        runtime_policy = getattr(runtime, "executor_policy", {}) or {}
        merged_options = dict(options or {})
        command = str(merged_options.get("command") or runtime_policy.get("command") or runtime_policy.get("framework") or self.framework_name)
        prompt = self.build_prompt(runtime, request)
        resolved_command = self._resolve_command_path(command)
        return [resolved_command, "-p", prompt, "--output-format", "json"], env

    def parse_response(self, completed: subprocess.CompletedProcess[str]) -> LlmResponse:
        stdout = (completed.stdout or "").strip()
        payload = self._maybe_parse_json(stdout)
        if isinstance(payload, dict):
            content = str(payload.get("content") or payload.get("result") or stdout)
            return LlmResponse(content=content, raw=payload)

        return LlmResponse(
            content=stdout,
            raw={
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "returncode": completed.returncode,
            },
        )

    def build_prompt(self, runtime: RuntimeBundle, request: LlmRequest) -> str:
        user_messages = "\n\n".join(message.content for message in request.messages if message.content)
        sections = []
        if user_messages:
            sections.append(f"[USER_MESSAGE]\n{user_messages}")
        sections.extend(section.strip() for section in (request.system_prompt, request.context_prompt) if section.strip())
        return "\n\n".join(sections) or f"Work inside the workspace root: {runtime.workspace_root}"

    def _resolve_command_path(self, command: str) -> str:
        candidates = [command]
        if os.name == "nt":
            candidates.extend([f"{command}.cmd", f"{command}.exe", f"{command}.ps1"])

        for candidate in candidates:
            resolved = shutil.which(candidate)
            if resolved:
                return resolved
        return command

    def _maybe_parse_json(self, value: str) -> dict[str, object] | None:
        if not value:
            return None
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
