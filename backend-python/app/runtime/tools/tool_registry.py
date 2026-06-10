from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable

from pydantic import BaseModel


def default_invoke(tool: object, runtime: Any, arguments: Any) -> object:
    return tool.run(
        run_id=runtime.agent_run.run_id,
        workspace_id=runtime.agent_run.workspace_id,
        runtime=runtime,
        arguments=arguments,
    )


@dataclass(slots=True)
class ToolSpec:
    name: str
    tool: object
    definition: dict[str, Any] | None = None
    request_model: type[BaseModel] | None = None
    invoke: Callable[[object, Any, Any], object] = default_invoke
    default_tool_choice: bool = False


@dataclass(slots=True)
class ToolRegistry:
    specs: dict[str, ToolSpec] = field(default_factory=dict)

    def register(self, spec: ToolSpec) -> None:
        self.specs[spec.name] = spec

    def get_spec(self, tool_name: str) -> ToolSpec | None:
        return self.specs.get(tool_name)

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        return [spec.definition for spec in self.specs.values() if spec.definition is not None]

    def get_default_tool_choice(self) -> dict[str, Any] | None:
        for spec in self.specs.values():
            if spec.default_tool_choice and spec.definition is not None:
                return {"type": "function", "function": {"name": spec.name}}
        return None

    def dispatch(self, runtime: Any, tool_calls: list[dict[str, Any]]) -> None:
        for tool_call in tool_calls:
            function = tool_call.get("function", {})
            tool_name = function.get("name")
            if not tool_name:
                continue

            spec = self.get_spec(tool_name)
            if spec is None:
                continue

            arguments = self._parse_arguments(function.get("arguments", "{}"))
            if spec.request_model is not None:
                arguments = spec.request_model.model_validate(arguments)

            spec.invoke(spec.tool, runtime, arguments)

    @property
    def tools(self) -> dict[str, object]:
        return {name: spec.tool for name, spec in self.specs.items()}

    def _parse_arguments(self, raw_arguments: object) -> Any:
        payload = self._maybe_load_json(raw_arguments)
        return self._normalize_nested_json(payload)

    def _normalize_nested_json(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: self._normalize_nested_json(self._maybe_load_json(item)) for key, item in value.items()}

        if isinstance(value, list):
            return [self._normalize_nested_json(self._maybe_load_json(item)) for item in value]

        return value

    def _maybe_load_json(self, value: Any) -> Any:
        if not isinstance(value, str):
            return value

        stripped = value.strip()
        if not stripped.startswith(("{", "[")):
            return value

        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
