"""
Strands agent runtime factory.

Builds a Strands Agent wired to Google Gemini, shared by StrandsLLMProvider
(structured extraction, app/services/llm/strands_provider.py) and
InvestigationAgentService (tool-using agent, app/services/agents/investigation_agent.py).
Centralizing construction here means both call sites configure the model
identically and both can be swapped out from one place in tests.
"""
from typing import Callable, List, Optional

from strands import Agent
from strands.models.gemini import GeminiModel

from app.core.config import settings


def is_strands_configured() -> bool:
    """True if a Gemini API key is present for the Strands runtime to use."""
    return bool(settings.GEMINI_API_KEY and settings.GEMINI_API_KEY.strip())


def build_gemini_agent(system_prompt: str, tools: Optional[List[Callable]] = None) -> Agent:
    """
    Constructs a Strands Agent backed by Gemini, using the same model and
    generation parameters as the legacy GeminiLLMProvider.
    """
    if not is_strands_configured():
        raise ValueError("Strands runtime is not configured: GEMINI_API_KEY is missing.")

    model = GeminiModel(
        client_args={"api_key": settings.GEMINI_API_KEY},
        model_id=settings.LLM_MODEL,
        params={
            "temperature": settings.LLM_TEMPERATURE,
            "max_output_tokens": settings.LLM_MAX_TOKENS_PER_REQUEST,
        },
    )
    return Agent(model=model, system_prompt=system_prompt, tools=tools or [])
