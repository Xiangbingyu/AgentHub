from app.runtime.mcp.resolver import McpRuntimeResolver


def test_mcp_runtime_resolver_returns_disabled_runtime_by_default() -> None:
    runtime = McpRuntimeResolver().resolve({"enabled": False, "servers": []})

    assert runtime["enabled"] is False
    assert runtime["tools"] == []
