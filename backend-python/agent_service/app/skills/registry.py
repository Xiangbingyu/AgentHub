from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re


@dataclass(slots=True)
class SkillRegistry:
    skills: dict[str, dict[str, str]] = field(default_factory=dict)

    def build(self, *, workspace_root: str, skill_config: dict[str, object]) -> "SkillRegistry":
        loaded: dict[str, dict[str, str]] = {}
        for root in skill_config.get("paths", []):
            self._load_from_root(loaded, Path(str(root)))
        return SkillRegistry(skills=loaded)

    def get(self, name: str) -> dict[str, str]:
        return self.skills[name]

    def render_available_skills(self) -> str:
        available = sorted(self.skills.values(), key=lambda item: item["name"])
        if not available:
            return ""
        lines = ["<available_skills>"]
        for item in available:
            lines.extend(
                [
                    "  <skill>",
                    f"    <name>{item['name']}</name>",
                    f"    <description>{item['description']}</description>",
                    "  </skill>",
                ]
            )
        lines.append("</available_skills>")
        return "\n".join(lines)

    def _load_from_root(self, skills: dict[str, dict[str, str]], root: Path) -> None:
        if not root.exists():
            return
        for path in root.glob("*/SKILL.md"):
            content = path.read_text(encoding="utf-8")
            match = re.match(
                r"---\nname:\s*(?P<name>[^\n]+)\ndescription:\s*(?P<description>[^\n]+)\n---\n\n(?P<body>.*)",
                content,
                re.DOTALL,
            )
            if not match:
                continue
            name = match.group("name").strip()
            skills[name] = {
                "name": name,
                "description": match.group("description").strip(),
                "content": match.group("body").strip(),
                "location": str(path),
            }
