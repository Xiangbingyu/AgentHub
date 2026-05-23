from app.config import get_settings
from app.llm.llm_executor import LlmExecutor
from app.llm.llm_types import LlmMessage, LlmRequest


def test_llm_executor_can_call_model() -> None:
    settings = get_settings()
    executor = LlmExecutor()
    response = executor.complete(
        LlmRequest(
            system_prompt="You are a helpful assistant.",
            tool_prompt="",
            context_prompt="",
            messages=[LlmMessage(role="user", content="Say hello in one short sentence.")],
            model=settings.test_model or "",
        )
    )

    assert response.content
