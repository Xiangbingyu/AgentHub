from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from typing import TYPE_CHECKING

from app.llm.llm_types import LlmRequest, LlmResponse

if TYPE_CHECKING:
    from app.runtime.runtime_assembler import RuntimeBundle


class OpenCodeAdapter:
    framework_name = "opencode"

    def build_command(
        self,
        runtime: RuntimeBundle,
        request: LlmRequest,
        env: dict[str, str],
        options: dict[str, object] | None = None,
    ) -> tuple[list[str], dict[str, str]]:
        runtime_policy = getattr(runtime, "executor_config", {}) or {}
        merged_options = dict(runtime_policy.get("framework_options") or {})
        merged_options.update(options or {})
        command = str(merged_options.get("command") or runtime_policy.get("command") or runtime_policy.get("framework") or self.framework_name)
        prompt = self.build_prompt(runtime, request)
        dangerously_skip_permissions = bool(merged_options.get("dangerously_skip_permissions", True))
        resolved_command = self._resolve_command_path(command)
        command_args = [resolved_command, "run", prompt, "--format", "json"]
        if dangerously_skip_permissions:
            command_args.append("--dangerously-skip-permissions")
        return command_args, env

    def parse_response(self, completed: subprocess.CompletedProcess[str]) -> LlmResponse:
        stdout = (completed.stdout or "").strip()
        events = self._parse_event_stream(stdout)
        if events:
            content = self._extract_final_text(events) or stdout
            return LlmResponse(content=content, raw={"events": events, "stdout": completed.stdout})

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
        prompt = "\n\n".join(sections) or f"Work inside the workspace root: {runtime.workspace_root}"
        return re.sub(r"\s+", " ", prompt).strip()

    def _resolve_command_path(self, command: str) -> str:
        if os.name == "nt":
            candidates = [f"{command}.cmd", f"{command}.exe", command, f"{command}.ps1"]
        else:
            candidates = [command]

        for candidate in candidates:
            resolved = shutil.which(candidate)
            if resolved:
                return resolved
        return command

    def _parse_event_stream(self, value: str) -> list[dict[str, object]]:
        events: list[dict[str, object]] = []
        if not value:
            return events
        for line in value.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                events.append(parsed)
        return events

    def _extract_final_text(self, events: list[dict[str, object]]) -> str:
        for event in reversed(events):
            part = event.get("part")
            if isinstance(part, dict) and part.get("type") == "text":
                text = part.get("text")
                if isinstance(text, str) and text.strip():
                    return text
        return ""
