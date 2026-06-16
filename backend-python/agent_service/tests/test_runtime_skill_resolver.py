from agent_service.app.runtime.skills.resolver import SkillRuntimeResolver


def test_skill_runtime_resolver_builds_registry_from_snapshot(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    skill_dir = workspace / ".agenthub" / "skills" / "local-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: local-skill\ndescription: local test skill\n---\n\n# Local Skill\n",
        encoding="utf-8",
    )

    runtime = SkillRuntimeResolver().resolve(
        workspace_root=str(workspace),
        skill_config={
            "builtins_enabled": False,
            "paths": [str(workspace / ".agenthub" / "skills")],
            "include_global": False,
            "allowed_skills": [],
        },
    )

    assert runtime.get("local-skill")["name"] == "local-skill"
