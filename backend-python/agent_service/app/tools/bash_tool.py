from __future__ import annotations

import fnmatch
import shlex
import subprocess
import sys
import threading
from pathlib import Path

from agent_service.app.schemas.bash_tool import BashToolRequest


class BashTool:
    DEFAULT_TIMEOUT_MS = 120000
    MAX_OUTPUT_CHARS = 12000
    # 中断/超时轮询粒度：足够灵敏（打断在 ~100ms 内生效），又不空转烧 CPU。
    POLL_INTERVAL_SECONDS = 0.1

    def run(self, *, runtime, arguments: BashToolRequest | dict, **_kwargs):
        request = arguments if isinstance(arguments, BashToolRequest) else BashToolRequest.model_validate(arguments)
        cwd = self._resolve_workdir(runtime.workspace_root, request.workdir)
        self._check_policy(runtime.tool_config, request.command)
        timeout_ms = request.timeout or self.DEFAULT_TIMEOUT_MS
        command = self._build_command(request.command)
        cancel_event = getattr(runtime, "cancel_event", None)
        return self._execute(request, command, cwd, timeout_ms, cancel_event)

    def _execute(self, request, command, cwd, timeout_ms, cancel_event):
        """Popen + 轮询执行：边等子进程，边盯超时与中断信号。

        - 中断信号置位：杀掉进程树，返回 aborted（抢占式打断的核心）。
        - 超过 timeout：杀掉进程树，返回 timed_out。
        - 正常结束：返回 exit_code 与输出。
        子进程 stdin 接 DEVNULL，避免 input() 类命令永久阻塞。
        """
        process = subprocess.Popen(
            command,
            cwd=str(cwd),
            shell=isinstance(command, str),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
        )

        # 另起线程 communicate() 收全输出，主线程只负责轮询状态，避免管道写满死锁。
        captured: dict[str, bytes] = {}

        def _drain() -> None:
            out, err = process.communicate()
            captured["stdout"] = out or b""
            captured["stderr"] = err or b""

        drainer = threading.Thread(target=_drain, daemon=True)
        drainer.start()

        timeout_seconds = timeout_ms / 1000
        waited = 0.0
        aborted = False
        timed_out = False
        while drainer.is_alive():
            if cancel_event is not None and cancel_event.is_set():
                aborted = True
                break
            if waited >= timeout_seconds:
                timed_out = True
                break
            drainer.join(self.POLL_INTERVAL_SECONDS)
            waited += self.POLL_INTERVAL_SECONDS

        if aborted or timed_out:
            self._kill_process_tree(process)
            drainer.join(self.POLL_INTERVAL_SECONDS)
            return self._terminal_metadata(
                request, cwd, captured, aborted=aborted, timed_out=timed_out, timeout_ms=timeout_ms
            )

        output, truncated = self._truncate_output(captured.get("stdout"), captured.get("stderr"))
        if process.returncode == 0 and output == "(no output)":
            output = "Command completed successfully with no output."
        return {
            "title": request.description,
            "output": output,
            "metadata": {
                "exit_code": process.returncode,
                "timed_out": False,
                "aborted": False,
                "truncated": truncated,
                "cwd": str(cwd),
                "command": request.command,
            },
        }

    def _terminal_metadata(self, request, cwd, captured, *, aborted, timed_out, timeout_ms):
        output, truncated = self._truncate_output(captured.get("stdout"), captured.get("stderr"))
        if aborted:
            suffix = "Command aborted by a new incoming message"
        else:
            suffix = f"Command timed out after {timeout_ms} ms"
        output = suffix if output == "(no output)" else f"{output}\n\n{suffix}"
        return {
            "title": request.description,
            "output": output,
            "metadata": {
                "exit_code": None,
                "timed_out": timed_out,
                "aborted": aborted,
                "truncated": truncated,
                "cwd": str(cwd),
                "command": request.command,
            },
        }

    def _kill_process_tree(self, process: subprocess.Popen) -> None:
        if process.poll() is not None:
            return
        if sys.platform == "win32":
            # Windows 下 PowerShell 会派生子进程，必须按 PID 杀整棵树。
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                capture_output=True,
                stdin=subprocess.DEVNULL,
            )
        else:
            process.kill()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass


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
