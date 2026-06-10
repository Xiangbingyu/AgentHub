from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.runtime.runtime_assembler import RuntimeBundle


@dataclass(slots=True)
class InstructionItem:
    source: str
    content: str
    level: str


@dataclass(slots=True)
class InstructionView:
    items: list[InstructionItem] = field(default_factory=list)


class InstructionResolver:
    def resolve(self, runtime: RuntimeBundle) -> InstructionView:
        workspace_root = Path(runtime.workspace_root)
        candidates = [workspace_root / "AGENTS.md"]
        if (runtime.executor_config.get("framework") or "").strip().lower() == "claude":
            candidates.append(workspace_root / "CLAUDE.md")

        items: list[InstructionItem] = []
        for path in candidates:
            if not path.exists() or not path.is_file():
                continue
            content = path.read_text(encoding="utf-8").strip()
            if not content:
                continue
            items.append(
                InstructionItem(
                    source=str(path),
                    content=content,
                    level="project",
                )
            )
        return InstructionView(items=items)
