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
def configure(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("LLM_MODEL", "openai/gpt-oss-120b")
    monkeypatch.setenv("GROQ_API_KEY", "secret-key")
    monkeypatch.setenv("LLM_MAX_RETRIES", "1")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_groq_builds_expected_request_and_parses_answer(configure: None) -> None:
    recorder = Recorder({"choices": [{"message": {"content": PAYLOAD}}]})
    result = LLMClient(http_post=recorder).generate_structured("Prompt", {"a": 1}, Answer)
    assert result == Answer(value=7)
    call = recorder.calls[0]
    assert call["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert call["headers"]["Authorization"] == "Bearer secret-key"
    assert call["json"]["model"] == "openai/gpt-oss-120b"
    assert call["json"]["response_format"] == {"type": "json_object"}


def test_custom_endpoint_cannot_redirect_groq_credentials(configure: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_BASE_URL", "https://proxy.example")
    get_settings.cache_clear()
    recorder = Recorder({"choices": [{"message": {"content": PAYLOAD}}]})
    LLMClient(http_post=recorder).generate_structured("p", {}, Answer)
    assert recorder.calls[0]["url"] == "https://api.groq.com/openai/v1/chat/completions"


def test_non_groq_provider_is_refused(configure: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    get_settings.cache_clear()
    with pytest.raises(LLMError, match="Seul le fournisseur Groq"):
        LLMClient(http_post=Recorder({})).generate_structured("p", {}, Answer)


def test_missing_api_key_is_refused_before_any_call(
    configure: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "  ")
    get_settings.cache_clear()
    recorder = Recorder({})
    with pytest.raises(LLMError, match="Clé API Groq absente"):
        LLMClient(http_post=recorder).generate_structured("p", {}, Answer)
    assert recorder.calls == []


def test_unexpected_response_shape_becomes_llm_error(configure: None) -> None:
    with pytest.raises(LLMError, match="inattendue"):
        LLMClient(http_post=Recorder({"unexpected": True})).generate_structured("p", {}, Answer)


def test_http_error_does_not_leak_key_or_url(configure: None) -> None:
    with pytest.raises(LLMError) as raised:
        LLMClient(http_post=Recorder({"error": "x"}, status=500)).generate_structured(
            "p", {}, Answer
        )
    assert "secret-key" not in str(raised.value)
    assert "groq.com" not in str(raised.value)


def test_invalid_json_is_retried_then_succeeds(configure: None) -> None:
    recorder = Recorder(
        [
            {"choices": [{"message": {"content": "pas du json"}}]},
            {"choices": [{"message": {"content": PAYLOAD}}]},
        ]
    )
    result = LLMClient(http_post=recorder).generate_structured("p", {}, Answer)
    assert result.value == 7
    assert len(recorder.calls) == 2


def test_schema_violation_gives_up_after_retries(configure: None) -> None:
    recorder = Recorder({"choices": [{"message": {"content": json.dumps({"value": "x"})}}]})
    with pytest.raises(LLMError, match="invalide après 2"):
        LLMClient(http_post=recorder).generate_structured("p", {}, Answer)
    assert len(recorder.calls) == 2


def test_rate_limit_retries_with_bounded_backoff(configure: None) -> None:
    responses = [
        httpx.Response(
            429, headers={"retry-after": "3"}, request=httpx.Request("POST", "http://test")
        ),
        httpx.Response(
            200,
            json={"choices": [{"message": {"content": PAYLOAD}}]},
            request=httpx.Request("POST", "http://test"),
        ),
    ]
    delays: list[float] = []

    def post(url: str, **kwargs: Any) -> httpx.Response:
        return responses.pop(0)

    result = LLMClient(http_post=post, sleep=delays.append).generate_structured("p", {}, Answer)
    assert result.value == 7
    assert delays == [3.0]
