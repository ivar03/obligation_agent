import pytest
from pydantic import BaseModel

from app.ops.shadow_compare import compare_providers


class _Answer(BaseModel):
    answer: str


class _StubProvider:
    def __init__(self, name, answer=None, error=None, delay=0.0):
        self.provider_name = name
        self._answer = answer
        self._error = error
        self._delay = delay

    async def generate_structured(self, system_prompt, user_prompt, schema_cls,
                                  temperature=0.0, max_tokens=2048, timeout_seconds=5.0):
        import asyncio
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._error:
            raise self._error
        return schema_cls(answer=self._answer)


@pytest.mark.asyncio
async def test_comparison_reports_agreement():
    providers = {"gemini": _StubProvider("gemini", "same"),
                 "strands": _StubProvider("strands", "same")}

    result = await compare_providers(
        "sys", "usr", _Answer, provider_names=("gemini", "strands"),
        provider_lookup=providers.get,
    )

    assert result.agreed is True
    assert result.results["gemini"].ok is True
    assert result.results["strands"].ok is True


@pytest.mark.asyncio
async def test_comparison_reports_disagreement():
    providers = {"gemini": _StubProvider("gemini", "one"),
                 "strands": _StubProvider("strands", "two")}

    result = await compare_providers(
        "sys", "usr", _Answer, provider_names=("gemini", "strands"),
        provider_lookup=providers.get,
    )

    assert result.agreed is False


@pytest.mark.asyncio
async def test_comparison_survives_one_provider_failing():
    providers = {"gemini": _StubProvider("gemini", "one"),
                 "strands": _StubProvider("strands", error=RuntimeError("quota"))}

    result = await compare_providers(
        "sys", "usr", _Answer, provider_names=("gemini", "strands"),
        provider_lookup=providers.get,
    )

    assert result.agreed is False
    assert result.results["strands"].ok is False
    assert "quota" in result.results["strands"].error
    assert result.results["gemini"].ok is True


@pytest.mark.asyncio
async def test_silent_degradation_is_never_reported_as_agreement():
    """An unconfigured provider degrades to the mock. Two mocks agreeing says
    nothing about gemini vs strands, and must not read as a green cutover signal."""
    mock_stand_in = _StubProvider("mock", "same")
    providers = {"gemini": mock_stand_in, "strands": mock_stand_in}

    result = await compare_providers(
        "sys", "usr", _Answer, provider_names=("gemini", "strands"),
        provider_lookup=providers.get,
    )

    assert result.agreed is False
    assert sorted(result.degraded) == ["gemini", "strands"]
    assert result.results["gemini"].resolved_provider == "mock"
