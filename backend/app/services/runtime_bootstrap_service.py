from __future__ import annotations

from agentscope.agent import ContextConfig, ReActConfig
from agentscope.app.storage import RedisStorage
from agentscope.app.storage._model._agent import AgentData, AgentRecord
from agentscope.app.storage._model._session import ChatModelConfig
from agentscope.credential import DashScopeCredential, OpenAICredential
from redis.asyncio import Redis

from app.config import get_settings
from app.domain.teams.models import AgentTemplateRecord


class RuntimeBootstrapService:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def ensure_default_credential(self, user_id: str) -> str:
        settings = get_settings()
        storage = RedisStorage(connection_pool=self._redis.connection_pool)
        async with storage:
            if settings.agentscope_provider == "dashscope":
                api_key = settings.dashscope_api_key
                if api_key is None:
                    raise ValueError(
                        "dashscope_api_key is required for dashscope provider"
                    )
                credential = DashScopeCredential(
                    id="default-dashscope-credential",
                    name="Default DashScope Credential",
                    api_key=api_key,
                )
            elif settings.agentscope_provider == "openai":
                api_key = settings.openai_api_key
                if api_key is None:
                    raise ValueError(
                        "openai_api_key is required for openai provider"
                    )
                credential = OpenAICredential(
                    id="default-openai-credential",
                    name="Default OpenAI Credential",
                    api_key=api_key,
                    base_url=settings.openai_base_url,
                )
            else:
                raise ValueError(f"Unsupported provider: {settings.agentscope_provider}")

            return await storage.upsert_credential(user_id, credential)

    async def ensure_runtime_agent(
        self,
        user_id: str,
        agent_template: AgentTemplateRecord,
    ) -> str:
        storage = RedisStorage(connection_pool=self._redis.connection_pool)
        async with storage:
            existing = await storage.get_agent(user_id, agent_template.agent_id)
            if existing is not None:
                return existing.id

            record = AgentRecord(
                id=agent_template.agent_id,
                user_id=user_id,
                source="user",
                data=AgentData(
                    id=agent_template.agent_id,
                    name=agent_template.name,
                    system_prompt=agent_template.system_prompt,
                    context_config=ContextConfig(),
                    react_config=ReActConfig(),
                ),
            )
            return await storage.upsert_agent(user_id, record)

    async def build_default_chat_model_config(self, user_id: str) -> ChatModelConfig:
        credential_id = await self.ensure_default_credential(user_id)
        settings = get_settings()
        return ChatModelConfig(
            type=f"{settings.agentscope_provider}_credential",
            credential_id=credential_id,
            model=settings.agentscope_model,
            parameters={},
        )
