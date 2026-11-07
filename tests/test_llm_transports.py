"""Tests du transport HTTP Groq avec un faux httpx.post (aucun réseau)."""

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


def groq_body(content: str = PAYLOAD) -> dict[str, Any]:
    return {"choices": [{"message": {"content": content}}]}


class Recorder:
    def __init__(
        self,
        bodies: list[Any] | Any,
        status: int = 200,
        headers: dict[str, str] | None = None,
    ):
        self.bodies = bodies if isinstance(bodies, list) else [bodies]
        self.status = status
        self.headers = headers or {}
        self.calls: list[dict[str, Any]] = []

    def __call__(self, url: str, **kwargs: Any) -> httpx.Response:
        self.calls.append({"url": url, **kwargs})
        index = min(len(self.calls) - 1, len(self.bodies) - 1)
        return httpx.Response(
            self.status,
            json=self.bodies[index],
            headers=self.headers,
            request=httpx.Request("POST", url),
        )


@pytest.fixture
def configure(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "secret-key")
    monkeypatch.setenv("LLM_MODEL", "openai/gpt-oss-120b")
    monkeypatch.setenv("LLM_MAX_RETRIES", "1")
    monkeypatch.setenv("LLM_BASE_URL", "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_groq_builds_expected_request_and_parses_answer(configure: None) -> None:
    recorder = Recorder(groq_body())
    result = LLMClient(http_post=recorder).generate_structured("Prompt", {"a": 1}, Answer)

    assert result == Answer(value=7)
    call = recorder.calls[0]
    assert call["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert call["headers"]["Authorization"] == "Bearer secret-key"
    assert call["json"]["model"] == "openai/gpt-oss-120b"
    assert call["json"]["response_format"] == {"type": "json_object"}
    request = json.loads(call["json"]["messages"][0]["content"])
    assert request["prompt"] == "Prompt"
    assert request["input"] == {"a": 1}
    assert request["schema"]["title"] == "Answer"


def test_groq_base_url_override_is_used(configure: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_BASE_URL", "https://groq-proxy.example.test/v1/")
    get_settings.cache_clear()
    recorder = Recorder(groq_body())

    LLMClient(http_post=recorder).generate_structured("p", {}, Answer)

    assert recorder.calls[0]["url"] == "https://groq-proxy.example.test/v1/chat/completions"


def test_groq_api_key_is_required_before_http_call(
    configure: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GROQ_API_KEY", " ")
    get_settings.cache_clear()
    recorder = Recorder(groq_body())

    with pytest.raises(LLMError, match="GROQ_API_KEY"):
        LLMClient(http_post=recorder).generate_structured("p", {}, Answer)

    assert recorder.calls == []


@pytest.mark.parametrize("provider", ["openai", "anthropic", "gemini", "ollama"])
def test_non_groq_provider_is_rejected(
    provider: str,
    configure: None,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("LLM_PROVIDER", provider)
    get_settings.cache_clear()

    with pytest.raises(LLMError, match="Seul le fournisseur Groq"):
        LLMClient(http_post=Recorder(groq_body())).generate_structured("p", {}, Answer)


def test_unexpected_groq_response_shape_becomes_llm_error(configure: None) -> None:
    with pytest.raises(LLMError, match="Réponse inattendue"):
        LLMClient(http_post=Recorder({"unexpected": True})).generate_structured("p", {}, Answer)


def test_invalid_json_is_retried_then_succeeds(configure: None) -> None:
    recorder = Recorder([groq_body("pas du json"), groq_body()])
    result = LLMClient(http_post=recorder).generate_structured("p", {}, Answer)

    assert result.value == 7
    assert len(recorder.calls) == 2
    second_request = json.loads(recorder.calls[1]["json"]["messages"][0]["content"])
    assert second_request["previous_validation_error"]


def test_schema_violation_gives_up_after_retries(configure: None) -> None:
    recorder = Recorder(groq_body(json.dumps({"value": "not-an-int"})))

    with pytest.raises(LLMError, match="invalide après 2"):
        LLMClient(http_post=recorder).generate_structured("p", {}, Answer)

    assert len(recorder.calls) == 2


def test_http_error_does_not_leak_key_or_url(configure: None) -> None:
    recorder = Recorder({"error": "secret-key"}, status=500)

    with pytest.raises(LLMError) as raised:
        LLMClient(http_post=recorder).generate_structured("p", {}, Answer)

    assert "secret-key" not in str(raised.value)
    assert "api.groq.com" not in str(raised.value)


def test_rate_limit_retries_with_bounded_backoff(configure: None, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LLM_RETRY_BACKOFF_SECONDS", "7")
    get_settings.cache_clear()
    responses = [
        httpx.Response(
            429,
            headers={"retry-after": "3"},
            json={"error": {"type": "rate_limit"}},
            request=httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions"),
        ),
        httpx.Response(
            200,
            json=groq_body(),
            request=httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions"),
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
