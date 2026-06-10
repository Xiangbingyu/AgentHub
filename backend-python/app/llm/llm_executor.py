from __future__ import annotations

import os
import subprocess
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Callable, Protocol

from app.config import get_settings
from app.llm.llm_types import LlmRequest, LlmResponse
from app.llm.openai_compatible_provider import OpenAICompatibleProvider

if TYPE_CHECKING:
    from app.runtime.runtime_assembler import RuntimeBundle


class AgentExecutor(ABC):
    @abstractmethod
    def execute(self, runtime: RuntimeBundle, request: LlmRequest) -> LlmResponse:
        raise NotImplementedError


class FrameworkAdapter(Protocol):
    def build_command(
        self,
        runtime: RuntimeBundle,
        request: LlmRequest,
        env: dict[str, str],
        options: dict[str, object] | None = None,
    ) -> tuple[list[str], dict[str, str]]: ...

    def parse_response(self, completed: subprocess.CompletedProcess[str]) -> LlmResponse: ...


def resolve_framework_adapter(framework: str | None) -> FrameworkAdapter:
    normalized = (framework or "").strip().lower()
    if normalized in {"", "claude", "claude_code"}:
        from app.llm.framework_adapters.claude_code_adapter import ClaudeCodeAdapter

        return ClaudeCodeAdapter()
    if normalized in {"opencode", "open_code"}:
        from app.llm.framework_adapters.opencode_adapter import OpenCodeAdapter

        return OpenCodeAdapter()
    if normalized == "codex":
        from app.llm.framework_adapters.codex_cli_adapter import CodexCliAdapter

        return CodexCliAdapter()
    raise ValueError(f"unsupported framework adapter: {framework}")


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
    def __init__(self, adapter_resolver: Callable[[str | None], FrameworkAdapter] | None = None) -> None:
        self.adapter_resolver = adapter_resolver or resolve_framework_adapter

    def execute(self, runtime: RuntimeBundle, request: LlmRequest) -> LlmResponse:
        policy = runtime.executor_policy
        framework = str(policy.get("framework") or "claude")
        cwd = policy.get("cwd") or runtime.workspace_root
        if not cwd:
            raise ValueError("workspace_root is required for framework executor")
        timeout_seconds = int(policy.get("timeout_seconds", 300))
        adapter = self.adapter_resolver(framework)
        command_args, env = adapter.build_command(runtime, request, self._build_env())
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
            raise RuntimeError(f"framework command not found: {framework}") from exc

        if completed.returncode != 0:
            raise RuntimeError(
                f"framework executor failed with exit code {completed.returncode}: {(completed.stderr or '').strip() or (completed.stdout or '').strip()}"
            )

        return adapter.parse_response(completed)

    def _build_env(self) -> dict[str, str]:
        return dict(os.environ)


class AgentExecutorFactory:
    def resolve(self, runtime: RuntimeBundle) -> AgentExecutor:
        if runtime.executor_policy.get("kind") == "framework_cli":
            return FrameworkCliExecutor()
        return InternalLlmExecutor()


class LlmExecutor(InternalLlmExecutor):
    pass
