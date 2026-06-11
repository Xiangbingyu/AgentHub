from app.mcp.service import McpService


def test_mcp_service_build_runtime_returns_disabled_shape() -> None:
    runtime = McpService().build_runtime({"enabled": False, "servers": []})

    assert runtime == {"enabled": False, "tools": []}


def test_mcp_service_normalizes_tool_names() -> None:
    service = McpService()
    specs = service.build_tool_specs(
        server_name="github",
        tools=[
            {
                "name": "search issues",
                "description": "Search GitHub issues",
                "input_schema": {"type": "object", "properties": {}},
            }
        ],
    )

    assert specs[0].name == "github__search_issues"
