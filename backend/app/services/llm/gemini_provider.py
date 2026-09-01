"""
Phase 20 / Phase 22 Official Google Gemini LLM Provider.

Implements BaseLLMProvider using the official google-genai SDK for production
natural-language obligation extraction, semantic event classification,
and grounded explanations via structured JSON generation.
"""

import json
import asyncio
from typing import Optional, Dict, Any, Type, TypeVar, List
from pydantic import BaseModel

from app.core.config import settings
from app.core.logging import logger
from app.services.llm.base import BaseLLMProvider
from app.schemas.llm import LLMProviderInfo

try:
    from google import genai
    from google.genai import types
    from google.genai.errors import APIError
    GENAI_AVAILABLE = True
except ImportError:
    genai = None  # type: ignore
    types = None  # type: ignore
    APIError = Exception  # type: ignore
    GENAI_AVAILABLE = False

T = TypeVar("T", bound=BaseModel)


class GeminiLLMProvider(BaseLLMProvider):
    """
    Production LLM Provider for Google Gemini API (gemini-1.5-flash, gemini-1.5-pro, etc.)
    using the official Google GenAI Python SDK.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        self._api_key = api_key or getattr(settings, "GEMINI_API_KEY", "") or ""
        self._model_name = model_name or getattr(settings, "LLM_MODEL", "gemini-1.5-flash")
        if self._model_name in ["mock-intelligence-v1", "gpt-4o", "gpt-4o-mini"]:
            # Default to gemini-1.5-flash if legacy model string present
            self._model_name = "gemini-1.5-flash"
        self._provider_name = "gemini"
        self._provider_version = "1.0.0"

    @property
    def provider_name(self) -> str:
        return self._provider_name

    @property
    def provider_version(self) -> str:
        return self._provider_version

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def capabilities(self) -> List[str]:
        return ["structured_json", "grounded_explanation", "evidence_interpretation", "fast_ack"]

    def is_configured(self) -> bool:
        """Returns True if an API key is present."""
        return bool(self._api_key and self._api_key.strip())

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
        Calls Google Gemini API via official google-genai async client with
        response_mime_type='application/json' and structured schema validation.
        """
        if not self.is_configured():
            raise ValueError("Gemini LLM provider is not configured: GEMINI_API_KEY is missing.")

        if not GENAI_AVAILABLE:
            raise RuntimeError("google-genai SDK is not installed in the environment.")

        # Embed schema property definitions in system instruction to guarantee schema compliance
        schema_json_sample = json.dumps(schema_cls.model_json_schema().get("properties", {}), indent=2)
        augmented_system = (
            f"{system_prompt}\n\n"
            f"You MUST respond ONLY with a valid JSON object matching these schema properties:\n"
            f"{schema_json_sample}"
        )

        client = genai.Client(api_key=self._api_key)

        config = types.GenerateContentConfig(
            system_instruction=augmented_system,
            response_mime_type="application/json",
            response_schema=schema_cls,
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        try:
            response = await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=self._model_name,
                    contents=user_prompt,
                    config=config,
                ),
                timeout=timeout_seconds,
            )

            raw_text = response.text
            if not raw_text or not raw_text.strip():
                raise ValueError("Gemini returned empty response text.")

            parsed_dict = json.loads(raw_text)
            return schema_cls.model_validate(parsed_dict)

        except asyncio.TimeoutError:
            logger.error(f"Gemini LLM request timed out after {timeout_seconds}s.")
            raise TimeoutError(f"Gemini LLM request timed out after {timeout_seconds}s.")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini JSON response: {e}")
            raise ValueError(f"Gemini response was not valid JSON: {e}")
        except Exception as e:
            err_str = str(e)
            if "API_KEY_INVALID" in err_str or "401" in err_str or "unauthenticated" in err_str.lower():
                raise PermissionError("Gemini API authentication failed: Invalid API key.")
            elif "RESOURCE_EXHAUSTED" in err_str or "429" in err_str or "quota" in err_str.lower():
                raise PermissionError("Gemini API rate limit or quota exceeded.")
            elif not isinstance(e, (TimeoutError, PermissionError, ValueError)):
                logger.error(f"Gemini provider error: {e}")
            raise

    async def health_check(self) -> LLMProviderInfo:
        """Returns non-secret diagnostic health info."""
        configured = self.is_configured()
        return LLMProviderInfo(
            provider_name=self._provider_name,
            provider_version=self._provider_version,
            model=self._model_name,
            capabilities=self.capabilities,
            healthy=configured,
        )
