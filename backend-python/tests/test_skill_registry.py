from app.skills.registry import SkillRegistry


def test_skill_registry_loads_workspace_skill(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    skill_dir = workspace / ".agenthub" / "skills" / "debugging"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: debugging\ndescription: Debug failures\n---\n\n# Debugging\n",
        encoding="utf-8",
    )

    registry = SkillRegistry().build(
        workspace_root=str(workspace),
        skill_config={
            "builtins_enabled": False,
            "paths": [str(workspace / ".agenthub" / "skills")],
            "include_global": False,
            "allowed_skills": [],
        },
    )

    assert registry.get("debugging")["description"] == "Debug failures"


def test_skill_registry_renders_available_skills_block(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    skill_dir = workspace / ".agenthub" / "skills" / "debugging"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: debugging\ndescription: Debug failures\n---\n\n# Debugging\n",
        encoding="utf-8",
    )

    registry = SkillRegistry().build(
        workspace_root=str(workspace),
        skill_config={
            "builtins_enabled": False,
            "paths": [str(workspace / ".agenthub" / "skills")],
            "include_global": False,
            "allowed_skills": [],
        },
    )

    rendered = registry.render_available_skills()

    assert "<available_skills>" in rendered
    assert "<name>debugging</name>" in rendered
