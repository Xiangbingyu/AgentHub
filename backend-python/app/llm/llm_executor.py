from __future__ import annotations

import json
import os
import shutil
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

from app.config import get_settings
from app.llm.llm_types import LlmRequest, LlmResponse
from app.llm.openai_compatible_provider import OpenAICompatibleProvider

if TYPE_CHECKING:
    from app.runtime.runtime_assembler import RuntimeBundle


class AgentExecutor(ABC):
    @abstractmethod
    def execute(self, runtime: RuntimeBundle, request: LlmRequest) -> LlmResponse:
        raise NotImplementedError


class InternalLlmExecutor(AgentExecutor):
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.test_api_key or not settings.test_base_url or not settings.test_model:
            raise ValueError("TEST_API_KEY / TEST_BASE_URL / TEST_MODEL are required")
        self.provider = OpenAICompatibleProvider(
            api_key=settings.test_api_key,
            base_url=settings.test_base_url,
            model=settings.test_model,
        )

    def execute(self, runtime: RuntimeBundle, request: LlmRequest) -> LlmResponse:
        return self.provider.complete(request)

    def complete(self, request: LlmRequest) -> LlmResponse:
        return self.provider.complete(request)


class FrameworkCliExecutor(AgentExecutor):
    def execute(self, runtime: RuntimeBundle, request: LlmRequest) -> LlmResponse:
        policy = runtime.executor_policy
        command = policy.get("command") or policy.get("framework") or "claude"
        allowed_tools = ",".join(policy.get("framework_allowed_tools", []))
        permission_mode = policy.get("permission_mode")
        allow_dangerously_skip_permissions = bool(policy.get("allow_dangerously_skip_permissions", False))
        dangerously_skip_permissions = bool(policy.get("dangerously_skip_permissions", False))
        cwd = policy.get("cwd") or runtime.workspace_root
        if not cwd:
            raise ValueError("workspace_root is required for framework executor")
        timeout_seconds = int(policy.get("timeout_seconds", 300))
        prompt = self._build_framework_prompt(runtime, request)
        env = self._build_env()
        command_args, env = self._build_command(command, prompt, allowed_tools, permission_mode, allow_dangerously_skip_permissions, dangerously_skip_permissions, env)
        try:
            completed = subprocess.run(
                command_args,
                cwd=cwd,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds,
                check=False,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(f"framework command not found: {command}") from exc

        if completed.returncode != 0:
            raise RuntimeError(
                f"framework executor failed with exit code {completed.returncode}: {completed.stderr.strip() or completed.stdout.strip()}"
            )

        stdout = (completed.stdout or "").strip()
        payload = self._maybe_parse_json(stdout)
        if isinstance(payload, dict):
            content = str(payload.get("content") or payload.get("result") or stdout)
            raw = payload
        else:
            content = stdout
            raw = {
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "returncode": completed.returncode,
            }

        return LlmResponse(content=content, raw=raw)

    def _build_env(self) -> dict[str, str]:
        return dict(os.environ)

    def _build_command(
        self,
        command: str,
        prompt: str,
        allowed_tools: str,
        permission_mode: object,
        allow_dangerously_skip_permissions: bool,
        dangerously_skip_permissions: bool,
        env: dict[str, str],
    ) -> tuple[list[str], dict[str, str]]:
        if self._should_use_powershell_wrapper(command):
            return self._build_powershell_command(
                command,
                prompt,
                allowed_tools,
                permission_mode,
                allow_dangerously_skip_permissions,
                dangerously_skip_permissions,
                env,
            )

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

    def _build_powershell_command(
        self,
        command: str,
        prompt: str,
        allowed_tools: str,
        permission_mode: object,
        allow_dangerously_skip_permissions: bool,
        dangerously_skip_permissions: bool,
        env: dict[str, str],
    ) -> tuple[list[str], dict[str, str]]:
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

    def _build_framework_prompt(self, runtime: RuntimeBundle, request: LlmRequest) -> str:
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


class AgentExecutorFactory:
    def resolve(self, runtime: RuntimeBundle) -> AgentExecutor:
        if runtime.executor_policy.get("kind") == "framework_cli":
            return FrameworkCliExecutor()
        return InternalLlmExecutor()


class LlmExecutor(InternalLlmExecutor):
    pass
