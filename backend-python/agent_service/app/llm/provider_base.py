from __future__ import annotations

from abc import ABC, abstractmethod

from agent_service.app.llm.llm_types import LlmRequest, LlmResponse


class LlmProvider(ABC):
    @abstractmethod
    def complete(self, request: LlmRequest) -> LlmResponse:
        raise NotImplementedError
