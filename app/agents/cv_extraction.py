import logging
from pathlib import Path

from pydantic import BaseModel, Field

from app.agents.normalization import normalize_skills
from app.schemas.agent_outputs import ExtractedProfileOut
from app.services.llm import LLMClient, LLMError

logger = logging.getLogger(__name__)
_PROMPT = (Path(__file__).parent / "prompts" / "cv_extraction_agent.txt").read_text(
    encoding="utf-8"
)
_MAX_CV_TEXT = 20_000


class CVExtractionInput(BaseModel):
    cv_text: str = Field(min_length=1, max_length=100_000)


class CVExtractionAgentError(RuntimeError):
    """Erreur explicite de l'agent d'extraction du CV."""


class CVExtractionAgent:
    def __init__(self, llm_client: LLMClient, max_text_length: int = _MAX_CV_TEXT) -> None:
        if max_text_length < 1:
            raise ValueError("La limite du texte CV doit être positive.")
        self._llm_client = llm_client
        self._max_text_length = max_text_length

    def run(self, data: CVExtractionInput) -> ExtractedProfileOut:
        text = data.cv_text.strip()
        if not text:
            raise CVExtractionAgentError("Le CV est vide.")
        if len(text) > self._max_text_length:
            logger.warning(
                "CV tronqué avant extraction: longueur=%d limite=%d",
                len(text),
                self._max_text_length,
            )
            text = text[: self._max_text_length]
        input_data = f"<cv_non_fiable>\n{text}\n</cv_non_fiable>"
        try:
            result = self._llm_client.generate_structured(_PROMPT, input_data, ExtractedProfileOut)
            values = result.model_dump()
            values["skills"] = normalize_skills(values["skills"])
            return ExtractedProfileOut.model_validate(values)
        except (LLMError, ValueError, TypeError) as exc:
            logger.error("CVExtractionAgent échoué: %s", type(exc).__name__)
            raise CVExtractionAgentError("L'extraction du CV a échoué.") from exc


def max_cv_text_length() -> int:
    return _MAX_CV_TEXT
