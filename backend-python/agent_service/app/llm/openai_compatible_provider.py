from __future__ import annotations

import json
import threading
from typing import Any

import httpx

from agent_service.app.llm.llm_types import LlmRequest, LlmResponse


class OpenAICompatibleProvider:
    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    def complete(self, request: LlmRequest, cancel_event=None) -> LlmResponse:
        messages = [
            {"role": "system", "content": request.system_prompt},
            {"role": "system", "content": request.context_prompt},
            *(self._serialize_message(message) for message in request.messages),
        ]

        payload: dict[str, Any] = {
            "model": request.model or self.model,
            "messages": messages,
            "temperature": 0.2,
        }
        if request.tools:
            payload["tools"] = request.tools
        if request.tool_choice is not None:
            payload["tool_choice"] = request.tool_choice

        client = httpx.Client()
        canceller = None
        if cancel_event is not None:
            def _watch_cancel() -> None:
                cancel_event.wait()
                client.close()

            canceller = threading.Thread(target=_watch_cancel, daemon=True)
            canceller.start()

        response = client.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            content=json.dumps(payload),
            timeout=60.0,
        )
        response.raise_for_status()
        data = response.json()
        message = data["choices"][0]["message"]
        return LlmResponse(
            content=message.get("content", ""),
            tool_calls=message.get("tool_calls", []),
            raw=data,
        )

    def _serialize_message(self, message) -> dict[str, Any]:
        payload: dict[str, Any] = {"role": message.role, "content": message.content}
        if message.tool_calls:
            payload["tool_calls"] = message.tool_calls
        if message.tool_call_id:
            payload["tool_call_id"] = message.tool_call_id
        return payload
