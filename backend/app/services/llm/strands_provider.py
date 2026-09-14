"""
Strands-backed LLM provider.

Implements BaseLLMProvider by routing structured generation through a
Strands Agent (Gemini model) instead of calling google-genai directly.
Same contract as GeminiLLMProvider, so the existing call sites
(hybrid_extraction_service, semantic_event_interpreter, grounded_explanation_service)
need no changes to use it.
"""
import asyncio
from typing import List, Type, TypeVar

from pydantic import BaseModel
from strands.types.exceptions import ModelThrottledException

from app.core.config import settings
from app.core.logging import logger
from app.services.llm.base import BaseLLMProvider
from app.services.agents import runtime
from app.schemas.llm import LLMProviderInfo

T = TypeVar("T", bound=BaseModel)


class StrandsLLMProvider(BaseLLMProvider):
    """Routes structured generation through Strands' Gemini agent runtime."""

    def __init__(self, agent_factory=runtime.build_gemini_agent):
        self._agent_factory = agent_factory
        self._provider_name = "strands"
        self._provider_version = "1.0.0"

    @property
    def provider_name(self) -> str:
        return self._provider_name

    @property
    def provider_version(self) -> str:
        return self._provider_version

    @property
    def model_name(self) -> str:
        return settings.LLM_MODEL

    @property
    def capabilities(self) -> List[str]:
        return ["structured_json", "grounded_explanation", "evidence_interpretation", "tool_use"]

    def is_configured(self) -> bool:
        return runtime.is_strands_configured()

    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        schema_cls: Type[T],
        temperature: float = 0.0,
        max_tokens: int = 2048,
        timeout_seconds: float = 5.0,
    ) -> T:
        if not self.is_configured():
            raise ValueError("Strands LLM provider is not configured: GEMINI_API_KEY is missing.")

        agent = self._agent_factory(system_prompt)

        try:
            return await asyncio.wait_for(
                agent.structured_output_async(schema_cls, user_prompt),
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError:
            logger.error(f"Strands LLM request timed out after {timeout_seconds}s.")
            raise TimeoutError(f"Strands LLM request timed out after {timeout_seconds}s.")
        except ModelThrottledException as e:
            logger.error(f"Strands/Gemini rate limit or quota exceeded: {e}")
            raise PermissionError("Strands/Gemini rate limit or quota exceeded.")
        except Exception as e:
            logger.error(f"Strands provider error: {e}")
            raise

    async def health_check(self) -> LLMProviderInfo:
        configured = self.is_configured()
        return LLMProviderInfo(
            provider_name=self._provider_name,
            provider_version=self._provider_version,
            model=self.model_name,
            capabilities=self.capabilities,
            healthy=configured,
        )