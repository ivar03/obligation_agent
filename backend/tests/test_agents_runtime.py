import pytest

from app.services.agents import runtime


def test_build_gemini_agent_requires_api_key(monkeypatch):
    monkeypatch.setattr(runtime.settings, "GEMINI_API_KEY", "")

    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        runtime.build_gemini_agent("You are a test agent.")


def test_build_gemini_agent_wires_model_and_prompt(monkeypatch):
    captured = {}

    class FakeGeminiModel:
        def __init__(self, client_args, model_id, params):
            captured["client_args"] = client_args
            captured["model_id"] = model_id
            captured["params"] = params

    class FakeAgent:
        def __init__(self, model, system_prompt, tools):
            captured["model"] = model
            captured["system_prompt"] = system_prompt
            captured["tools"] = tools

    monkeypatch.setattr(runtime, "GeminiModel", FakeGeminiModel)
    monkeypatch.setattr(runtime, "Agent", FakeAgent)
    monkeypatch.setattr(runtime.settings, "GEMINI_API_KEY", "test-key-123")
    monkeypatch.setattr(runtime.settings, "LLM_MODEL", "gemini-2.5-flash")

    agent = runtime.build_gemini_agent("You are a test agent.", tools=[])

    assert captured["model_id"] == "gemini-2.5-flash"
    assert captured["client_args"] == {"api_key": "test-key-123"}
    assert isinstance(captured["model"], FakeGeminiModel)
    assert captured["system_prompt"] == "You are a test agent."
    assert captured["tools"] == []
    assert isinstance(agent, FakeAgent)
