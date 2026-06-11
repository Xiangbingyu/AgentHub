from types import SimpleNamespace

from app.tools.skill_tool import SkillTool


def test_skill_tool_loads_skill_from_runtime_registry() -> None:
    runtime = SimpleNamespace(
        skill_registry=SimpleNamespace(
            get=lambda name: {
                "name": name,
                "description": "Debug failures",
                "content": "# Debugging",
                "location": "built-in",
            }
        )
    )

    result = SkillTool().run(runtime=runtime, arguments={"name": "debugging"})

    assert result["name"] == "debugging"
    assert "Debug failures" in result["content"]
    assert "<skill_content name=\"debugging\">" in result["content"]
