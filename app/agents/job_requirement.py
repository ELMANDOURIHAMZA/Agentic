import logging
from pathlib import Path

from pydantic import BaseModel, Field

from app.agents.normalization import normalize_skills
from app.schemas.agent_outputs import StructuredRequirementsOut
from app.services.llm import LLMClient, LLMError

logger = logging.getLogger(__name__)
_PROMPT = (Path(__file__).parent / "prompts" / "job_requirement_agent.txt").read_text(
    encoding="utf-8"
)


class JobRequirementInput(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=10000)
    required_degree: str = Field(default="", max_length=300)
    minimum_experience_years: float | None = Field(default=None, ge=0, le=80)
    required_skills: list[str] = Field(default_factory=list, max_length=100)
    preferred_skills: list[str] = Field(default_factory=list, max_length=100)
    required_certifications: list[str] = Field(default_factory=list, max_length=50)
    languages: list[str] = Field(default_factory=list, max_length=30)
    other_requirements: str = Field(default="", max_length=5000)


class JobRequirementAgentError(RuntimeError):
    """Erreur explicite de l'agent de structuration des exigences."""


class JobRequirementAgent:
    def __init__(self, llm_client: LLMClient) -> None:
        self._llm_client = llm_client

    def run(self, data: JobRequirementInput) -> StructuredRequirementsOut:
        payload = data.model_dump(mode="json")
        input_data = f"<donnees_offre>\n{payload}\n</donnees_offre>"
        try:
            result = self._llm_client.generate_structured(
                _PROMPT, input_data, StructuredRequirementsOut
            )
            return self._preserve_structured_fields(data, result)
        except (LLMError, ValueError, TypeError) as exc:
            logger.error("JobRequirementAgent échoué: %s", type(exc).__name__)
            raise JobRequirementAgentError("La structuration des exigences a échoué.") from exc

    @staticmethod
    def _preserve_structured_fields(
        data: JobRequirementInput, result: StructuredRequirementsOut
    ) -> StructuredRequirementsOut:
        values = result.model_dump()
        if data.required_degree.strip():
            values["required_degree"] = data.required_degree.strip()
        if data.minimum_experience_years is not None:
            values["minimum_experience_years"] = data.minimum_experience_years
        for field in (
            "required_skills",
            "preferred_skills",
            "required_certifications",
            "languages",
        ):
            source = getattr(data, field)
            if source:
                values[field] = normalize_skills(source) if "skills" in field else source
        if data.other_requirements.strip():
            values["other_requirements"] = data.other_requirements.strip()
        return StructuredRequirementsOut.model_validate(values)
