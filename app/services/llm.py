import json
import logging
import time
from collections.abc import Callable
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from app.config import get_settings

logger = logging.getLogger(__name__)
OutputModel = TypeVar("OutputModel", bound=BaseModel)
Transport = Callable[[str, dict[str, Any], float], Any]


class LLMError(RuntimeError):
    """Erreur explicite d'appel ou de validation du fournisseur LLM."""


class LLMRateLimitError(LLMError):
    """Limitation temporaire du fournisseur LLM, réessayable."""

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


DEFAULT_BASE_URLS = {
    "ollama": "http://127.0.0.1:11434",
    "openai": "https://api.openai.com",
    "anthropic": "https://api.anthropic.com",
    "gemini": "https://generativelanguage.googleapis.com",
}


class LLMClient:
    def __init__(
        self,
        transport: Transport | None = None,
        http_post: Callable[..., Any] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._transport = transport
        self._http_post = http_post
        self._sleep = sleep

    def generate_structured(
        self,
        prompt: str,
        input_data: Any,
        schema: type[OutputModel],
    ) -> OutputModel:
        settings = get_settings()
        provider = settings.llm_provider.casefold().strip()
        if provider not in {"anthropic", "openai", "gemini", "ollama"}:
            raise LLMError(f"Fournisseur LLM non supporté: {settings.llm_provider}")
        if provider != "ollama" and not (settings.llm_api_key or "").strip():
            raise LLMError(f"Clé API absente pour le fournisseur {provider}.")

        last_error: str | None = None
        max_attempts = settings.llm_max_retries + 1
        for attempt in range(max_attempts):
            try:
                raw = self._generate(provider, prompt, input_data, schema, last_error)
                payload = json.loads(raw) if isinstance(raw, str) else raw
                return schema.model_validate(payload)
            except (json.JSONDecodeError, TypeError, ValidationError) as exc:
                last_error = str(exc)
                if attempt + 1 == max_attempts:
                    raise LLMError(
                        f"Sortie LLM invalide après {max_attempts} tentative(s)."
                    ) from exc
            except LLMRateLimitError as exc:
                if attempt + 1 == max_attempts:
                    raise LLMError(
                        f"Limite du fournisseur atteinte après {max_attempts} tentative(s)."
                    ) from exc
                settings = get_settings()
                delay = exc.retry_after or (settings.llm_retry_backoff_seconds * (2**attempt))
                self._sleep(min(delay, 60.0))
            except LLMError:
                raise
            except Exception as exc:
                raise LLMError("Erreur lors de l'appel au fournisseur LLM.") from exc
        raise LLMError("Le fournisseur LLM n'a produit aucune sortie.")

    def _generate(
        self,
        provider: str,
        prompt: str,
        input_data: Any,
        schema: type[OutputModel],
        previous_error: str | None,
    ) -> Any:
        request = {
            "prompt": prompt,
            "input": input_data,
            "schema": schema.model_json_schema(),
            "previous_validation_error": previous_error,
        }
        if self._transport is not None:
            return self._transport(provider, request, get_settings().llm_timeout_seconds)
        return self._generate_with_provider(provider, request)

    def _generate_with_provider(self, provider: str, request: dict[str, Any]) -> Any:
        import httpx

        settings = get_settings()
        post = self._http_post or httpx.post
        base = (settings.llm_base_url or DEFAULT_BASE_URLS[provider]).rstrip("/")
        try:
            if provider == "ollama":
                response = post(
                    f"{base}/api/generate",
                    json={
                        "model": settings.llm_model,
                        "prompt": json.dumps(request),
                        "format": "json",
                    },
                    timeout=settings.llm_timeout_seconds,
                )
                response.raise_for_status()
                return response.json()["response"]

            headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
            if provider == "openai":
                response = post(
                    f"{base}/v1/chat/completions",
                    headers=headers,
                    json={
                        "model": settings.llm_model,
                        "response_format": {"type": "json_object"},
                        "messages": [{"role": "user", "content": json.dumps(request)}],
                    },
                    timeout=settings.llm_timeout_seconds,
                )
                response.raise_for_status()
                return response.json()["choices"][0]["message"]["content"]

            if provider == "anthropic":
                response = post(
                    f"{base}/v1/messages",
                    headers={
                        "x-api-key": settings.llm_api_key or "",
                        "anthropic-version": "2023-06-01",
                    },
                    json={
                        "model": settings.llm_model,
                        "max_tokens": 4096,
                        "messages": [{"role": "user", "content": json.dumps(request)}],
                    },
                    timeout=settings.llm_timeout_seconds,
                )
                response.raise_for_status()
                return response.json()["content"][0]["text"]

            response = post(
                f"{base}/v1beta/models/{settings.llm_model}:generateContent",
                params={"key": settings.llm_api_key},
                json={"contents": [{"parts": [{"text": json.dumps(request)}]}]},
                timeout=settings.llm_timeout_seconds,
            )
            response.raise_for_status()
            return response.json()["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise LLMError("Réponse inattendue du fournisseur LLM.") from exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                retry_after: float | None = None
                raw_retry_after = exc.response.headers.get("retry-after")
                if raw_retry_after:
                    try:
                        retry_after = max(0.0, float(raw_retry_after))
                    except ValueError:
                        retry_after = None
                raise LLMRateLimitError("Limite du fournisseur LLM.", retry_after) from exc
            raise LLMError("Erreur HTTP du fournisseur LLM.") from exc
        except httpx.HTTPError as exc:
            raise LLMError("Erreur HTTP du fournisseur LLM.") from exc
