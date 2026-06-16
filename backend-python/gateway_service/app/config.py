from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "gateway_service"
    app_version: str = "0.1.0"
    # 用 127.0.0.1 而非 localhost：localhost 在 Windows 上会解析出 IPv6(::1)+IPv4
    # 两条记录，httpx 先试 ::1（uvicorn 默认只监听 IPv4）超时再回退，每请求多 ~2s。
    agent_service_base_url: str = "http://127.0.0.1:8000"
    cors_allow_origins: list[str] = ["http://localhost:5173"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
