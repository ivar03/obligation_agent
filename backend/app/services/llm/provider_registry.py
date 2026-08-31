"""
Phase 20 LLM Provider Registry.

Manages registered LLM providers (Mock, OpenAI, self-hosted/local, etc.),
active provider selection, discovery, and health diagnostics.
"""

from typing import Dict, Optional, List
from app.core.config import settings
from app.services.llm.base import BaseLLMProvider
from app.services.llm.mock_provider import MockLLMProvider
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
        if target not in cls._providers:
            # Fallback to mock provider if unknown
            if "mock" in cls._providers:
                return cls._providers["mock"]
            mock_inst = MockLLMProvider()
            cls.register(mock_inst)
            return mock_inst
        return cls._providers[target]

    @classmethod
    def set_active_provider(cls, name: str):
        target = name.lower()
        if target in ["dev_mock", "mock_llm", "mock"]:
            target = "mock"
        if target in cls._providers:
            cls._active_provider_name = target
        else:
            # Safe fallback to mock if unknown provider configured in environment
            cls._active_provider_name = "mock"

    @classmethod
    def get_active_provider_name(cls) -> str:
        return cls._active_provider_name

    @classmethod
    def list_providers(cls) -> List[str]:
        return list(cls._providers.keys())

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


# Initialize default mock provider in registry
default_mock_provider = MockLLMProvider()
LLMProviderRegistry.register(default_mock_provider)
LLMProviderRegistry.set_active_provider(settings.LLM_PROVIDER or "mock")

