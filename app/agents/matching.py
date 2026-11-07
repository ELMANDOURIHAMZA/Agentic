import json
import logging
import re
import unicodedata
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from app.config import get_settings
from app.schemas.agent_outputs import (
    DocumentVerificationOut,
    ExtractedProfileOut,
    MatchingCriterionOut,
    MatchingOut,
    StructuredRequirementsOut,
)
from app.services.llm import LLMClient, LLMError

logger = logging.getLogger(__name__)
_PROMPT = (Path(__file__).parent / "prompts" / "matching_agent.txt").read_text(encoding="utf-8")

DEFAULT_MATCHING_WEIGHTS = {
    "required_skills": 40.0,
    "experience": 20.0,
    "degree": 15.0,
    "preferred_skills": 10.0,
    "languages": 5.0,
    "documents": 10.0,
}


def validate_matching_weights(weights: dict[str, float] = DEFAULT_MATCHING_WEIGHTS) -> None:
    if round(sum(weights.values()), 6) != 100:
        raise ValueError("Les pondérations du matching doivent totaliser 100.")


def configured_matching_weights() -> dict[str, float]:
    settings = get_settings()
    weights = {
        "required_skills": settings.matching_required_skills_weight,
        "experience": settings.matching_experience_weight,
        "degree": settings.matching_degree_weight,
        "preferred_skills": settings.matching_preferred_skills_weight,
        "languages": settings.matching_languages_weight,
        "documents": settings.matching_documents_weight,
    }
    validate_matching_weights(weights)
    return weights


class MatchingInput(BaseModel):
    requirements: StructuredRequirementsOut
    profile: ExtractedProfileOut
    document_verification: DocumentVerificationOut


Verdict = Literal["match", "partiel", "absent"]


class SemanticCriterionOut(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    verdict: Verdict
    justification: str = Field(default="", max_length=1000)
    evidence: list[str] = Field(default_factory=list, max_length=10)


class SemanticEvaluationOut(BaseModel):
    criteria: list[SemanticCriterionOut] = Field(default_factory=list, max_length=200)


class MatchingAgentError(RuntimeError):
    """Erreur explicite de l'agent de matching."""


# Unification des variantes arabes courantes (alef, ya, ta marbuta) et suppression du tatweel.
_ARABIC_FOLD = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ة": "ه", "ـ": None})


def _norm(value: str) -> str:
    """Normalise un texte multilingue (français, anglais, arabe) pour comparer sans accent."""
    decomposed = unicodedata.normalize("NFKD", value)
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    plain = plain.translate(_ARABIC_FOLD).casefold()
    return re.sub(r"\s+", " ", re.sub(r"[^\w+#.]+|_", " ", plain)).strip()


def _profile_text(profile: ExtractedProfileOut) -> str:
    values = [
        *profile.education,
        *profile.diplomas,
        *profile.skills,
        *profile.certifications,
        *profile.languages,
        *profile.professional_contributions,
    ]
    values.extend(
        item
        for experience in profile.experiences
        for item in (experience.position, experience.employer, str(experience.duration_months))
    )
    values.extend(
        item
        for project in profile.projects
        for item in (project.name, project.description, *project.technologies)
    )
    return _norm(" ".join(values))


def _verdict_score(verdict: Verdict) -> float:
    return {"match": 100.0, "partiel": 50.0, "absent": 0.0}[verdict]


class MatchingAgent:
    def __init__(self, llm_client: LLMClient) -> None:
        self._llm_client = llm_client
        self._weights = configured_matching_weights()

    def run(self, data: MatchingInput) -> MatchingOut:
        safe_profile = data.profile.model_copy(
            update={
                "declared_identity": data.profile.declared_identity.model_copy(
                    update={"first_name": None, "last_name": None, "birth_date": None}
                )
            }
        )
        verification_payload = json.dumps(
            {"compliance_level": data.document_verification.compliance_level}
        )
        request = (
            f"<exigences>\n{data.requirements.model_dump_json()}\n</exigences>\n"
            f"<profil_non_fiable>\n{safe_profile.model_dump_json(exclude_none=True)}\n</profil_non_fiable>\n"
            f"<verification>\n{verification_payload}\n</verification>"
        )
        try:
            semantic = self._llm_client.generate_structured(_PROMPT, request, SemanticEvaluationOut)
        except (LLMError, ValueError, TypeError) as exc:
            logger.error("MatchingAgent échoué: %s", type(exc).__name__)
            raise MatchingAgentError("L'évaluation du matching a échoué.") from exc
        return self._calculate(data, semantic)

    def _calculate(self, data: MatchingInput, semantic: SemanticEvaluationOut) -> MatchingOut:
        profile_text = _profile_text(data.profile)
        evaluations = {item.name: self._verified(item, profile_text) for item in semantic.criteria}
        active = self._active_criteria(data.requirements)
        active_total = sum(self._weights[name] for name in active)
        details: list[MatchingCriterionOut] = []
        weighted_score = 0.0
        matching: list[str] = []
        missing: list[str] = []

        for criterion in active:
            score, justification, evidence = self._criterion_score(
                criterion, data, evaluations, matching, missing
            )
            effective_weight = self._weights[criterion] / active_total * 100
            details.append(
                MatchingCriterionOut(
                    name=criterion,
                    score=score,
                    weight=effective_weight,
                    justification=justification,
                    evidence=evidence,
                )
            )
            weighted_score += score * effective_weight / 100
        return MatchingOut(
            global_score=round(max(0.0, min(100.0, weighted_score)), 1),
            criteria=details,
            matching_skills=list(dict.fromkeys(matching)),
            missing_skills=list(dict.fromkeys(missing)),
        )

    @staticmethod
    def _active_criteria(requirements: StructuredRequirementsOut) -> list[str]:
        active = ["documents"]
        if requirements.required_skills:
            active.append("required_skills")
        if requirements.minimum_experience_years > 0:
            active.append("experience")
        if requirements.required_degree.strip():
            active.append("degree")
        if requirements.preferred_skills:
            active.append("preferred_skills")
        if requirements.languages:
            active.append("languages")
        return active

    @staticmethod
    def _verified(item: SemanticCriterionOut, profile_text: str) -> SemanticCriterionOut:
        if item.verdict != "absent" and not item.evidence:
            return item.model_copy(update={"verdict": "absent"})
        normalized = [_norm(evidence) for evidence in item.evidence]
        if any(not text or text not in profile_text for text in normalized):
            return item.model_copy(update={"verdict": "absent", "evidence": []})
        return item

    def _criterion_score(
        self,
        criterion: str,
        data: MatchingInput,
        evaluations: dict[str, SemanticCriterionOut],
        matching: list[str],
        missing: list[str],
    ) -> tuple[float, str, list[str]]:
        if criterion == "documents":
            return (
                data.document_verification.compliance_level,
                "Conformité documentaire déterministe.",
                [],
            )
        if criterion == "experience":
            years = sum(item.duration_months for item in data.profile.experiences) / 12
            required = data.requirements.minimum_experience_years
            return (
                min(100.0, years / required * 100),
                f"{years:.1f} année(s) pour {required:.1f} exigée(s).",
                [],
            )
        if criterion == "degree":
            return self._aggregate("degree", evaluations)
        if criterion == "languages":
            return self._aggregate_items(
                "language", data.requirements.languages, evaluations, matching, missing
            )
        if criterion == "required_skills":
            return self._aggregate_items(
                "required_skill",
                data.requirements.required_skills,
                evaluations,
                matching,
                missing,
            )
        return self._aggregate_items(
            "preferred_skill",
            data.requirements.preferred_skills,
            evaluations,
            matching,
            missing,
        )

    @staticmethod
    def _aggregate(
        name: str, evaluations: dict[str, SemanticCriterionOut]
    ) -> tuple[float, str, list[str]]:
        item = evaluations.get(name)
        if item is None:
            return 0.0, "Aucune évaluation vérifiable.", []
        return _verdict_score(item.verdict), item.justification, item.evidence

    def _aggregate_items(
        self,
        prefix: str,
        values: list[str],
        evaluations: dict[str, SemanticCriterionOut],
        matching: list[str],
        missing: list[str],
    ) -> tuple[float, str, list[str]]:
        scores: list[float] = []
        evidence: list[str] = []
        for value in values:
            item = evaluations.get(f"{prefix}:{value}")
            score = _verdict_score(item.verdict) if item else 0.0
            scores.append(score)
            if score:
                matching.append(value)
                evidence.extend(item.evidence if item else [])
            else:
                missing.append(value)
        return sum(scores) / len(scores), "Moyenne des verdicts par élément.", evidence
