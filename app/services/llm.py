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
GROQ_BASE_URL = "https://api.groq.com/openai"


class LLMError(RuntimeError):
    """Erreur explicite d'appel ou de validation de Groq."""


class LLMRateLimitError(LLMError):
    """Limitation temporaire de Groq, réessayable."""

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


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
        if settings.llm_provider.casefold().strip() != "groq":
            raise LLMError("Seul le fournisseur Groq est supporté.")
        if not (settings.llm_api_key or "").strip():
            raise LLMError("Clé API Groq absente.")

        last_error: str | None = None
        max_attempts = settings.llm_max_retries + 1
        for attempt in range(max_attempts):
            try:
                raw = self._generate(prompt, input_data, schema, last_error)
                payload = json.loads(raw) if isinstance(raw, str) else raw
                return schema.model_validate(payload)
            except (json.JSONDecodeError, TypeError, ValidationError) as exc:
                last_error = str(exc)
                if attempt + 1 == max_attempts:
                    raise LLMError(
                        f"Sortie Groq invalide après {max_attempts} tentative(s)."
                    ) from exc
            except LLMRateLimitError as exc:
                if attempt + 1 == max_attempts:
                    raise LLMError(
                        f"Limite Groq atteinte après {max_attempts} tentative(s)."
                    ) from exc
                settings = get_settings()
                delay = exc.retry_after or (settings.llm_retry_backoff_seconds * (2**attempt))
                self._sleep(min(delay, 60.0))
            except LLMError:
                raise
            except Exception as exc:
                raise LLMError("Erreur lors de l'appel à Groq.") from exc
        raise LLMError("Groq n'a produit aucune sortie.")

    def _generate(
        self,
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
            return self._transport("groq", request, get_settings().llm_timeout_seconds)
        return self._generate_with_groq(request)

    def _generate_with_groq(self, request: dict[str, Any]) -> Any:
        import httpx

        settings = get_settings()
        post = self._http_post or httpx.post
        base = (settings.llm_base_url or GROQ_BASE_URL).rstrip("/")
        try:
            response = post(
                f"{base}/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                json={
                    "model": settings.llm_model or "openai/gpt-oss-120b",
                    "response_format": {"type": "json_object"},
                    "messages": [{"role": "user", "content": json.dumps(request)}],
                },
                timeout=settings.llm_timeout_seconds,
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise LLMError("Réponse inattendue de Groq.") from exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                retry_after: float | None = None
                raw_retry_after = exc.response.headers.get("retry-after")
                if raw_retry_after:
                    try:
                        retry_after = max(0.0, float(raw_retry_after))
                    except ValueError:
                        retry_after = None
                raise LLMRateLimitError("Limite Groq.", retry_after) from exc
            raise LLMError("Erreur HTTP de Groq.") from exc
        except httpx.HTTPError as exc:
            raise LLMError("Erreur HTTP de Groq.") from exc
