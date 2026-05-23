from __future__ import annotations


def build_plan_tool_prompt() -> str:
    return (
        "Create and maintain a structured plan snapshot for the current run. "
        "Use this tool when you need to create or update the current execution plan. "
        "Always submit the full plan snapshot, not a patch. The plan contains title, goal, summary, "
        "and a complete steps list. Step states are pending, in_progress, completed, or cancelled. "
        "The tool will overwrite the existing plan snapshot and sync the rendered plan document."
    )
