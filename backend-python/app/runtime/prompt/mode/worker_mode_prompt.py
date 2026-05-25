from __future__ import annotations


def build_worker_mode_prompt() -> str:
    return (
        "worker is responsible for task execution; when asked to create or update a file, "
        "write the intended content to disk and do not leave an empty placeholder file"
    )
