from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from app.llm.llm_types import LlmRequest, LlmResponse

if TYPE_CHECKING:
    from app.runtime.runtime_assembler import RuntimeBundle


class ClaudeCodeAdapter:
    framework_name = "claude"

    def build_command(
        self,
        runtime: RuntimeBundle,
        request: LlmRequest,
        env: dict[str, str],
    ) -> tuple[list[str], dict[str, str]]:
        policy = runtime.executor_policy
        options = dict(policy.get("framework_options") or {})
        command = policy.get("command") or policy.get("framework") or self.framework_name
        prompt = self.build_prompt(runtime, request)
        allowed_tools = ",".join(options.get("allowed_tools") or ["Read", "Edit", "Bash", "Write"])
        permission_mode = options.get("permission_mode", policy.get("permission_mode"))
        allow_dangerously_skip_permissions = bool(
            options.get("allow_dangerously_skip_permissions", policy.get("allow_dangerously_skip_permissions", False))
        )
        dangerously_skip_permissions = bool(
            options.get("dangerously_skip_permissions", policy.get("dangerously_skip_permissions", False))
        )

        if self._should_use_powershell_wrapper(command):
            env = dict(env)
            env["CLAUDE_PROMPT"] = prompt
            command_line = f"{command} -p $env:CLAUDE_PROMPT"
            if allowed_tools:
                command_line += f" --allowedTools {allowed_tools}"
            if permission_mode:
                command_line += f" --permission-mode {permission_mode}"
            if allow_dangerously_skip_permissions:
                command_line += " --allow-dangerously-skip-permissions"
            if dangerously_skip_permissions:
                command_line += " --dangerously-skip-permissions"
            command_line += " --output-format json"
            return ["powershell", "-NoProfile", "-Command", command_line], env

        resolved_command = self._resolve_command_path(command)
        command_args = [resolved_command, "-p", prompt, "--output-format", "json"]
        if allowed_tools:
            command_args.extend(["--allowedTools", allowed_tools])
        if permission_mode:
            command_args.extend(["--permission-mode", str(permission_mode)])
        if allow_dangerously_skip_permissions:
            command_args.append("--allow-dangerously-skip-permissions")
        if dangerously_skip_permissions:
            command_args.append("--dangerously-skip-permissions")
        return command_args, env

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
        return user_messages or f"Work inside the workspace root: {runtime.workspace_root}"

    def _should_use_powershell_wrapper(self, command: str) -> bool:
        if os.name != "nt":
            return False
        return Path(command).name.lower().startswith("claude")

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
