from __future__ import annotations


def build_worker_mode_prompt() -> str:
    return (
        "worker is responsible for task execution; when asked to create, update, or delete files, "
        "you must use code_tool to perform the file change and must not only describe the change in text; "
        "write the intended content to disk and do not leave an empty placeholder file; "
        "when a task explicitly requires shell-based file relocation, copy, or rename operations, use bash_tool"
    )
