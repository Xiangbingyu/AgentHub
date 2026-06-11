from __future__ import annotations

from app.schemas.skill_tool import SkillToolRequest


class SkillTool:
    def run(self, *, runtime, arguments: SkillToolRequest | dict, **_kwargs):
        registry = getattr(runtime, "skill_registry", None)
        if registry is None:
            raise ValueError("skill_registry is required")

        request = arguments if isinstance(arguments, SkillToolRequest) else SkillToolRequest.model_validate(arguments)
        skill = registry.get(request.name)
        return {
            "name": skill["name"],
            "content": (
                f"<skill_content name=\"{skill['name']}\">\n"
                f"description: {skill['description']}\n\n"
                f"{skill['content']}\n\n"
                f"location: {skill['location']}\n"
                "</skill_content>"
            ),
        }
