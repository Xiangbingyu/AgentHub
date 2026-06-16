from __future__ import annotations

from importlib import metadata, util
from typing import Any

from app.config import Settings

_SERVICE_MODULES = ("apscheduler", "ag_ui_protocol")


def _has_module(module_name: str) -> bool:
    return util.find_spec(module_name) is not None


def _get_installed_version(package_name: str) -> str | None:
    try:
        return metadata.version(package_name)
    except metadata.PackageNotFoundError:
        return None


def _provider_key_name(provider: str) -> str:
    mapping = {
        "openai": "OPENAI_API_KEY",
        "dashscope": "DASHSCOPE_API_KEY",
    }
    return mapping.get(provider, f"{provider.upper()}_API_KEY")


def _is_provider_configured(settings: Settings) -> bool:
    provider = settings.agentscope_provider.lower()
    if provider == "openai":
        return settings.openai_api_key is not None
    if provider == "dashscope":
        return settings.dashscope_api_key is not None
    return False


def get_runtime_status(settings: Settings) -> dict[str, Any]:
    installed_version = _get_installed_version("agentscope")
    missing_service_dependencies = [
        module_name for module_name in _SERVICE_MODULES if not _has_module(module_name)
    ]
    provider = settings.agentscope_provider.lower()

    return {
        "installed": installed_version is not None,
        "version": installed_version,
        "provider": provider,
        "model": settings.agentscope_model,
        "mount_path": settings.agentscope_mount_path,
        "api_key_env": _provider_key_name(provider),
        "provider_configured": _is_provider_configured(settings),
        "service_extra_ready": not missing_service_dependencies,
        "missing_service_dependencies": missing_service_dependencies,
    }
