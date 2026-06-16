from agent_service.app.schemas.plan_tool import build_plan_tool_definition


def test_plan_tool_definition_exposes_function_schema() -> None:
    definition = build_plan_tool_definition()

    assert definition["type"] == "function"
    assert definition["function"]["name"] == "plan_tool"
    assert "parameters" in definition["function"]
