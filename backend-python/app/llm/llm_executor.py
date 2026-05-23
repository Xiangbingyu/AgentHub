from __future__ import annotations

from app.config import get_settings
from app.llm.llm_types import LlmRequest, LlmResponse
from app.llm.openai_compatible_provider import OpenAICompatibleProvider


class LlmExecutor:
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.test_api_key or not settings.test_base_url or not settings.test_model:
            raise ValueError("TEST_API_KEY / TEST_BASE_URL / TEST_MODEL are required")
        self.provider = OpenAICompatibleProvider(
            api_key=settings.test_api_key,
            base_url=settings.test_base_url,
            model=settings.test_model,
        )

    def complete(self, request: LlmRequest) -> LlmResponse:
        return self.provider.complete(request)
