"""
Phase 20 Base LLM Provider Abstraction.

Defines the vendor-neutral contract for all LLM providers (Mock, OpenAI, local, etc.).
Ensures the core application never depends on a single vendor SDK.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Type, TypeVar, List
from pydantic import BaseModel
from app.schemas.llm import LLMProviderInfo

T = TypeVar("T", bound=BaseModel)


class BaseLLMProvider(ABC):
    """Abstract interface for all LLM inference providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Machine-readable name of provider (e.g. 'mock', 'openai', 'local')."""
        pass

    @property
    @abstractmethod
    def provider_version(self) -> str:
        """Version string for the provider implementation."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Underlying model identifier (e.g. 'mock-intelligence-v1', 'gpt-4o')."""
        pass

    @property
    @abstractmethod
    def capabilities(self) -> List[str]:
        """List of supported capabilities (e.g. 'structured_json', 'grounded_explanation', 'streaming')."""
        pass

    @abstractmethod
    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        schema_cls: Type[T],
        temperature: float = 0.0,
        max_tokens: int = 2048,
        timeout_seconds: float = 5.0,
    ) -> T:
        """
        Executes inference and returns a validated Pydantic structured output.
        Must raise standard exceptions on timeout, rate limit, or inference failure.
        """
        pass

    @abstractmethod
    async def health_check(self) -> LLMProviderInfo:
        """Returns health status and metadata for diagnostics."""
        pass
