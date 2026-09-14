import asyncio
import pytest
from pydantic import BaseModel

from app.services.llm.strands_provider import StrandsLLMProvider


class _EchoSchema(BaseModel):
    answer: str


class _FakeAgent:
    def __init__(self, delay=0.0):
        self._delay = delay

    async def structured_output_async(self, output_model, prompt=None):
        if self._delay:
            await asyncio.sleep(self._delay)
        return output_model(answer=f"handled: {prompt}")


@pytest.mark.asyncio
async def test_generate_structured_returns_agent_result(monkeypatch):
    monkeypatch.setattr(
        "app.services.llm.strands_provider.runtime.is_strands_configured", lambda: True
    )
    provider = StrandsLLMProvider(agent_factory=lambda system_prompt: _FakeAgent())

    result = await provider.generate_structured(
        system_prompt="You extract obligations.",
        user_prompt="Ravi will send the report by Friday.",
        schema_cls=_EchoSchema,
        timeout_seconds=2.0,
    )

    assert isinstance(result, _EchoSchema)
    assert result.answer == "handled: Ravi will send the report by Friday."


@pytest.mark.asyncio
async def test_generate_structured_raises_value_error_when_unconfigured(monkeypatch):
    monkeypatch.setattr(
        "app.services.llm.strands_provider.runtime.is_strands_configured", lambda: False
    )
    provider = StrandsLLMProvider(agent_factory=lambda system_prompt: _FakeAgent())

    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        await provider.generate_structured(
            system_prompt="sys", user_prompt="usr", schema_cls=_EchoSchema
        )


@pytest.mark.asyncio
async def test_generate_structured_times_out(monkeypatch):
    monkeypatch.setattr(
        "app.services.llm.strands_provider.runtime.is_strands_configured", lambda: True
    )
    slow_agent = _FakeAgent(delay=1.0)
    provider = StrandsLLMProvider(agent_factory=lambda system_prompt: slow_agent)

    with pytest.raises(TimeoutError):
        await provider.generate_structured(
            system_prompt="sys", user_prompt="usr", schema_cls=_EchoSchema,
            timeout_seconds=0.05,
        )


@pytest.mark.asyncio
async def test_health_check_reports_configured_state(monkeypatch):
    monkeypatch.setattr(
        "app.services.llm.strands_provider.runtime.is_strands_configured", lambda: True
    )
    provider = StrandsLLMProvider(agent_factory=lambda system_prompt: _FakeAgent())

    info = await provider.health_check()

    assert info.provider_name == "strands"
    assert info.healthy is True
