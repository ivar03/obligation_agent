import pytest

from app.core.config import settings
from app.services.llm.provider_registry import LLMProviderRegistry
from app.services.llm.strands_provider import StrandsLLMProvider


@pytest.fixture(autouse=True)
def restore_active_provider():
    """The registry's active provider is global class state; put it back."""
    previous = LLMProviderRegistry.get_active_provider_name()
    yield
    LLMProviderRegistry.set_active_provider(previous)


def test_strands_provider_is_registered():
    assert "strands" in LLMProviderRegistry.list_providers()


def test_set_active_provider_strands_when_configured(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key")
    LLMProviderRegistry.set_active_provider("strands")

    assert LLMProviderRegistry.get_active_provider_name() == "strands"
    assert isinstance(LLMProviderRegistry.get(), StrandsLLMProvider)


def test_strands_falls_back_to_mock_when_unconfigured(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    monkeypatch.setattr(settings, "LLM_FALLBACK_TO_DETERMINISTIC", True)
    LLMProviderRegistry.set_active_provider("strands")

    assert LLMProviderRegistry.get().provider_name == "mock"


def test_runtime_status_reports_strands(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key")
    LLMProviderRegistry.set_active_provider("strands")

    status = LLMProviderRegistry.get_runtime_status()

    assert status["provider_name"] == "strands"
    assert status["service_status"] == "ready"
    assert status["api_key_configured"] is True
