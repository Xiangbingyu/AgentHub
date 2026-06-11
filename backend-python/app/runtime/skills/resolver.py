from __future__ import annotations

from app.skills.registry import SkillRegistry


class SkillRuntimeResolver:
    def __init__(self, registry: SkillRegistry | None = None) -> None:
        self.registry = registry or SkillRegistry()

    def resolve(self, *, workspace_root: str, skill_config: dict[str, object]) -> SkillRegistry:
        return self.registry.build(workspace_root=workspace_root, skill_config=skill_config)
