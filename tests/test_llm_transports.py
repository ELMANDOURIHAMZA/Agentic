"""Tests des quatre transports HTTP LLM avec un faux ``httpx.post`` (aucun réseau)."""

import json
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from pydantic import BaseModel

from app.config import get_settings
from app.services.llm import LLMClient, LLMError


class Answer(BaseModel):
    value: int


PAYLOAD = json.dumps({"value": 7})
BODIES: dict[str, Any] = {
    "ollama": {"response": PAYLOAD},
    "openai": {"choices": [{"message": {"content": PAYLOAD}}]},
    "anthropic": {"content": [{"type": "text", "text": PAYLOAD}]},
    "gemini": {"candidates": [{"content": {"parts": [{"text": PAYLOAD}]}}]},
}
EXPECTED_URLS = {
    "ollama": "http://127.0.0.1:11434/api/generate",
    "openai": "https://api.openai.com/v1/chat/completions",
    "anthropic": "https://api.anthropic.com/v1/messages",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/models/m-1:generateContent",
}


class Recorder:
    def __init__(self, bodies: list[Any] | Any, status: int = 200) -> None:
        self.bodies = bodies if isinstance(bodies, list) else [bodies]
        self.status = status
        self.calls: list[dict[str, Any]] = []

    def __call__(self, url: str, **kwargs: Any) -> httpx.Response:
        self.calls.append({"url": url, **kwargs})
        body = self.bodies[min(len(self.calls) - 1, len(self.bodies) - 1)]
        return httpx.Response(self.status, json=body, request=httpx.Request("POST", url))


@pytest.fixture
def configure(monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    def _configure(provider: str, **extra: str) -> None:
        monkeypatch.setenv("LLM_PROVIDER", provider)
        monkeypatch.setenv("LLM_MODEL", "m-1")
        monkeypatch.setenv("LLM_API_KEY", "secret-key")
        monkeypatch.setenv("LLM_MAX_RETRIES", "1")
        monkeypatch.setenv("LLM_BASE_URL", "")
        for key, value in extra.items():
            monkeypatch.setenv(key, value)
        get_settings.cache_clear()

    yield _configure
    get_settings.cache_clear()


@pytest.mark.parametrize("provider", sorted(BODIES))
def test_each_provider_builds_expected_request_and_parses_answer(
    provider: str, configure: Any
) -> None:
    configure(provider)
    recorder = Recorder(BODIES[provider])
    result = LLMClient(http_post=recorder).generate_structured("Prompt", {"a": 1}, Answer)
    assert result == Answer(value=7)
    call = recorder.calls[0]
    assert call["url"] == EXPECTED_URLS[provider]
    sent = json.dumps(call["json"])
    assert "Prompt" in sent and '\\"schema\\"' in sent
    if provider == "openai":
        assert call["headers"]["Authorization"] == "Bearer secret-key"
        assert call["json"]["response_format"] == {"type": "json_object"}
    if provider == "anthropic":
        assert call["headers"]["x-api-key"] == "secret-key"
        assert call["headers"]["anthropic-version"]
    if provider == "gemini":
        assert call["params"] == {"key": "secret-key"}
    if provider == "ollama":
        assert call["json"]["format"] == "json"


def test_base_url_override_is_used(configure: Any) -> None:
    configure("ollama", LLM_BASE_URL="http://llm.internal:9999/")
    recorder = Recorder(BODIES["ollama"])
    LLMClient(http_post=recorder).generate_structured("p", {}, Answer)
    assert recorder.calls[0]["url"] == "http://llm.internal:9999/api/generate"


@pytest.mark.parametrize("provider", ["openai", "anthropic", "gemini"])
def test_missing_api_key_is_refused_before_any_call(provider: str, configure: Any) -> None:
    configure(provider, LLM_API_KEY="  ")
    recorder = Recorder(BODIES[provider])
    with pytest.raises(LLMError, match="Clé API absente"):
        LLMClient(http_post=recorder).generate_structured("p", {}, Answer)
    assert recorder.calls == []


@pytest.mark.parametrize("provider", sorted(BODIES))
def test_unexpected_response_shape_becomes_llm_error(provider: str, configure: Any) -> None:
    configure(provider)
    with pytest.raises(LLMError, match="inattendue"):
        LLMClient(http_post=Recorder({"unexpected": True})).generate_structured("p", {}, Answer)


def test_http_error_does_not_leak_key_or_url(configure: Any) -> None:
    configure("gemini")
    with pytest.raises(LLMError) as raised:
        LLMClient(http_post=Recorder({"error": "x"}, status=500)).generate_structured(
            "p", {}, Answer
        )
    assert "secret-key" not in str(raised.value)
    assert "googleapis" not in str(raised.value)


def test_invalid_json_is_retried_then_succeeds(configure: Any) -> None:
    configure("ollama")
    recorder = Recorder([{"response": "pas du json"}, BODIES["ollama"]])
    result = LLMClient(http_post=recorder).generate_structured("p", {}, Answer)
    assert result.value == 7
    assert len(recorder.calls) == 2
    assert "previous_validation_error" in json.loads(recorder.calls[1]["json"]["prompt"])


def test_schema_violation_gives_up_after_retries(configure: Any) -> None:
    configure("ollama")
    recorder = Recorder({"response": json.dumps({"value": "x"})})
    with pytest.raises(LLMError, match="invalide après 2"):
        LLMClient(http_post=recorder).generate_structured("p", {}, Answer)
    assert len(recorder.calls) == 2


def test_rate_limit_retries_with_bounded_backoff(configure: Any) -> None:
    configure("ollama", LLM_RETRY_BACKOFF_SECONDS="7")
    responses = [
        httpx.Response(
            429,
            headers={"retry-after": "3"},
            json={"error": {"type": "rate_limit"}},
            request=httpx.Request("POST", "http://test"),
        ),
        httpx.Response(
            200,
            json=BODIES["ollama"],
            request=httpx.Request("POST", "http://test"),
        ),
    ]
    calls: list[dict[str, Any]] = []
    delays: list[float] = []

    def post(url: str, **kwargs: Any) -> httpx.Response:
        calls.append({"url": url, **kwargs})
        return responses.pop(0)

    result = LLMClient(http_post=post, sleep=delays.append).generate_structured("p", {}, Answer)
    assert result.value == 7
    assert len(calls) == 2
    assert delays == [3.0]
