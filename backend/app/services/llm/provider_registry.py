"""
Phase 20 / Phase 22 LLM Provider Registry.

Manages registered LLM providers (Mock, Gemini, self-hosted/local, etc.),
active provider selection, discovery, and health diagnostics.
"""

from typing import Dict, Optional, List, Any
from app.core.config import settings
from app.services.llm.base import BaseLLMProvider
from app.services.llm.mock_provider import MockLLMProvider
from app.services.llm.gemini_provider import GeminiLLMProvider
from app.schemas.llm import LLMProviderInfo


class LLMProviderRegistry:
    """Registry and factory for LLM providers."""

    _providers: Dict[str, BaseLLMProvider] = {}
    _active_provider_name: str = "mock"

    @classmethod
    def register(cls, provider: BaseLLMProvider):
        cls._providers[provider.provider_name.lower()] = provider

    @classmethod
    def get(cls, name: Optional[str] = None) -> BaseLLMProvider:
        target = (name or cls._active_provider_name or "mock").lower()
        if target in cls._providers:
            provider = cls._providers[target]
            # If Gemini was selected but is not configured with an API key, fall back gracefully
            if target == "gemini" and isinstance(provider, GeminiLLMProvider) and not provider.is_configured():
                if settings.LLM_FALLBACK_TO_DETERMINISTIC and "mock" in cls._providers:
                    return cls._providers["mock"]
            return provider
        
        # Fallback to mock provider if unknown
        if "mock" in cls._providers:
            return cls._providers["mock"]
        mock_inst = MockLLMProvider()
        cls.register(mock_inst)
        return mock_inst

    @classmethod
    def set_active_provider(cls, name: str):
        target = name.lower()
        if target in ["dev_mock", "mock_llm", "mock"]:
            target = "mock"
        if target in cls._providers:
            cls._active_provider_name = target
        else:
            cls._active_provider_name = "mock"

    @classmethod
    def get_active_provider_name(cls) -> str:
        return cls._active_provider_name

    @classmethod
    def list_providers(cls) -> List[str]:
        return list(cls._providers.keys())

    @classmethod
    def get_runtime_status(cls) -> Dict[str, Any]:
        """
        Returns safe, non-secret configuration and readiness status.
        Never reveals secret keys or partial secrets.
        """
        active_name = cls._active_provider_name
        active_prov = cls._providers.get(active_name)
        has_api_key = bool(settings.GEMINI_API_KEY and settings.GEMINI_API_KEY.strip())

        if not settings.LLM_ENABLED:
            service_status = "disabled"
            status_message = "LLM processing is disabled via LLM_ENABLED=false."
        elif active_name == "mock":
            service_status = "ready_mock"
            status_message = "Operating in offline deterministic mock mode."
        elif active_name == "gemini":
            if has_api_key:
                service_status = "ready"
                status_message = f"Google Gemini provider active with model '{active_prov.model_name if active_prov else settings.LLM_MODEL}'."
            else:
                service_status = "api_key_missing"
                status_message = "Google Gemini provider selected but GEMINI_API_KEY is not set in environment."
        else:
            service_status = "unknown_provider"
            status_message = f"Provider '{active_name}' is not recognized."

        return {
            "llm_enabled": settings.LLM_ENABLED,
            "provider_name": active_name,
            "model_name": active_prov.model_name if active_prov else settings.LLM_MODEL,
            "api_key_configured": has_api_key,
            "service_status": service_status,
            "status_message": status_message,
            "fallback_to_deterministic": settings.LLM_FALLBACK_TO_DETERMINISTIC,
            "timeout_seconds": settings.LLM_TIMEOUT_SECONDS,
            "temperature": settings.LLM_TEMPERATURE,
            "registered_providers": list(cls._providers.keys()),
        }

    @classmethod
    async def get_all_health(cls) -> List[LLMProviderInfo]:
        healths = []
        for p in cls._providers.values():
            try:
                h = await p.health_check()
                healths.append(h)
            except Exception:
                healths.append(
                    LLMProviderInfo(
                        provider_name=p.provider_name,
                        provider_version=p.provider_version,
                        model=p.model_name,
                        capabilities=p.capabilities,
                        healthy=False,
                    )
                )
        return healths


# Initialize providers in registry
default_mock_provider = MockLLMProvider()
default_gemini_provider = GeminiLLMProvider()

LLMProviderRegistry.register(default_mock_provider)
LLMProviderRegistry.register(default_gemini_provider)

# Set active provider based on environment configuration
configured_provider = (settings.LLM_PROVIDER or "mock").lower()
if configured_provider in ["gemini", "mock"]:
    LLMProviderRegistry.set_active_provider(configured_provider)
else:
    LLMProviderRegistry.set_active_provider("mock")
