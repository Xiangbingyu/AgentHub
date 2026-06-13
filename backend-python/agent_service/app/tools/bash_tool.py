from __future__ import annotations

import fnmatch
from pathlib import Path
import shlex
import subprocess
import sys

from agent_service.app.schemas.bash_tool import BashToolRequest


class BashTool:
    DEFAULT_TIMEOUT_MS = 120000
    MAX_OUTPUT_CHARS = 12000

    def run(self, *, runtime, arguments: BashToolRequest | dict, **_kwargs):
        request = arguments if isinstance(arguments, BashToolRequest) else BashToolRequest.model_validate(arguments)
        cwd = self._resolve_workdir(runtime.workspace_root, request.workdir)
        self._check_policy(runtime.tool_config, request.command)
        timeout_ms = request.timeout or self.DEFAULT_TIMEOUT_MS
        command = self._build_command(request.command)
        try:
            completed = subprocess.run(
                command,
                cwd=str(cwd),
                shell=isinstance(command, str),
                capture_output=True,
                timeout=timeout_ms / 1000,
            )
        except subprocess.TimeoutExpired as exc:
            output, truncated = self._truncate_output(exc.stdout, exc.stderr)
            if output == "(no output)":
                output = f"Command timed out after {timeout_ms} ms"
            else:
                output = output + f"\n\nCommand timed out after {timeout_ms} ms"
            return {
                "title": request.description,
                "output": output,
                "metadata": {
                    "exit_code": None,
                    "timed_out": True,
                    "aborted": False,
                    "truncated": truncated,
                    "cwd": str(cwd),
                    "command": request.command,
                },
            }
        output, truncated = self._truncate_output(completed.stdout, completed.stderr)
        return {
            "title": request.description,
            "output": output,
            "metadata": {
                "exit_code": completed.returncode,
                "timed_out": False,
                "aborted": False,
                "truncated": truncated,
                "cwd": str(cwd),
                "command": request.command,
            },
        }

    def _build_command(self, command: str) -> str | list[str]:
        if sys.platform == "win32":
            return [
                "powershell",
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                command,
            ]
        return command

    def _resolve_workdir(self, workspace_root: str, workdir: str | None) -> Path:
        root = Path(workspace_root).resolve()
        target = root if not workdir else Path(workdir)
        if not target.is_absolute():
            target = (root / target).resolve()
        else:
            target = target.resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"workdir escapes workspace root: {workdir}") from exc
        if not target.exists() or not target.is_dir():
            raise ValueError(f"workdir does not exist: {workdir}")
        return target

    def _check_policy(self, tool_config: dict, command: str) -> None:
        rules = ((tool_config or {}).get("command_policies") or {}).get("bash") or {"*": "allow"}
        for pattern in self._derive_patterns(command):
            action = self._resolve_rule_action(rules, pattern)
            if action == "deny":
                raise ValueError(f"bash command denied by policy: {pattern}")

    def _derive_patterns(self, command: str) -> list[str]:
        parts: list[str] = []
        for segment in self._split_segments(command):
            tokens = self._tokenize(segment)
            if not tokens:
                continue
            if len(tokens) >= 2:
                parts.append(f"{tokens[0]} {tokens[1]} *")
                continue
            parts.append(f"{tokens[0]} *")
        return parts or [command.strip()]

    def _split_segments(self, command: str) -> list[str]:
        normalized = command.replace("&&", ";").replace("||", ";")
        return [segment.strip() for segment in normalized.split(";") if segment.strip()]

    def _tokenize(self, segment: str) -> list[str]:
        try:
            return shlex.split(segment, posix=sys.platform != "win32")
        except ValueError:
            return segment.split()

    def _resolve_rule_action(self, rules: dict[str, str], pattern: str) -> str:
        action = "allow"
        for rule_pattern, rule_action in rules.items():
            if fnmatch.fnmatch(pattern, rule_pattern):
                action = rule_action
        return action

    def _truncate_output(self, stdout: str | bytes | None, stderr: str | bytes | None) -> tuple[str, bool]:
        stdout_text = self._normalize_stream(stdout)
        stderr_text = self._normalize_stream(stderr)
        output = stdout_text
        if stderr_text:
            output = f"{stdout_text}\n{stderr_text}" if stdout_text else stderr_text
        output = output.strip() or "(no output)"
        if len(output) <= self.MAX_OUTPUT_CHARS:
            return output, False
        return output[: self.MAX_OUTPUT_CHARS] + "\n\n...output truncated...", True

    def _normalize_stream(self, value: str | bytes | None) -> str:
        if value is None:
            return ""
        if isinstance(value, bytes):
            return value.decode("utf-8", "replace")
        return value
