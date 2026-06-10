from __future__ import annotations


def build_orchestrator_mode_prompt() -> str:
    return (
        "orchestrator is responsible for planning and plan maintenance; "
        "when planning depends on command-line inspection of files, directories, or other workspace state, "
        "you must call bash_tool to obtain that information and must not assume command output in plain text"
    )
