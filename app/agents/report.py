import logging
import math
import re
import unicodedata
from pathlib import Path

from pydantic import BaseModel

from app.schemas.agent_outputs import (
    DocumentVerificationOut,
    ExtractedProfileOut,
    MatchingOut,
    ReportOut,
    StructuredRequirementsOut,
)
from app.schemas.candidate import CandidateResultView, build_candidate_view
from app.services.llm import LLMClient, LLMError

logger = logging.getLogger(__name__)
_PROMPT = (Path(__file__).parent / "prompts" / "report_agent.txt").read_text(encoding="utf-8")
_HUMAN_REMINDER = "Le score est une aide à la décision ; la décision finale appartient à un humain."
_SENSITIVE_PATTERN = re.compile(
    r"(?<![a-z0-9])(?:cin|cin_number|birth_date|date de naissance)(?![a-z0-9])"
)


def _normalize_for_scan(text: str) -> str:
    """Minuscules sans accents : « CIN » est détecté, « médecin » ou « cinéma » ne le sont pas."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


class ReportInput(BaseModel):
    requirements: StructuredRequirementsOut
    profile: ExtractedProfileOut
    document_verification: DocumentVerificationOut
    matching: MatchingOut


class ReportAgentError(RuntimeError):
    """Erreur explicite de l'agent de rapport."""


class ReportAgent:
    def __init__(self, llm_client: LLMClient) -> None:
        self._llm_client = llm_client

    def run(self, data: ReportInput) -> ReportOut:
        safe_profile = data.profile.model_copy(
            update={
                "declared_identity": data.profile.declared_identity.model_copy(
                    update={"birth_date": None}
                )
            }
        )
        base_request = (
            f"<exigences>\n{data.requirements.model_dump_json()}\n</exigences>\n"
            f"<profil_non_fiable>\n{safe_profile.model_dump_json(exclude_none=True)}\n</profil_non_fiable>\n"
            f"<verification>\n{data.document_verification.model_dump_json()}\n</verification>\n"
            f"<matching>\n{data.matching.model_dump_json()}\n</matching>"
        )
        previous_error: str | None = None
        for _ in range(2):
            request = base_request
            if previous_error:
                request += (
                    f"\n<erreur_validation_precedente>\n{previous_error}\n"
                    "</erreur_validation_precedente>"
                )
            try:
                report = self._llm_client.generate_structured(_PROMPT, request, ReportOut)
                report = self._align_verified_fields(data, report)
                self._validate_report(data, report)
                return self._with_human_reminder(report)
            except ReportAgentError as exc:
                previous_error = str(exc)
                logger.warning("ReportAgent sortie rejetée: %s", type(exc).__name__)
            except (LLMError, ValueError, TypeError) as exc:
                logger.error("ReportAgent échoué: %s", type(exc).__name__)
                raise ReportAgentError("La génération du rapport a échoué.") from exc
        raise ReportAgentError("La génération du rapport a échoué après validation.")

    @staticmethod
    def _align_verified_fields(data: ReportInput, report: ReportOut) -> ReportOut:
        criteria = [
            ReportOut.Criterion(
                name=criterion.name,
                score=criterion.score,
                weight=criterion.weight,
                justification=criterion.justification,
                evidence=criterion.evidence,
            )
            for criterion in data.matching.criteria
        ]
        inconsistencies = [
            f"{item.field}: {item.cv_value} / {item.document_value}"
            for item in data.document_verification.inconsistencies
        ]
        return report.model_copy(update={"criteria": criteria, "inconsistencies": inconsistencies})

    @staticmethod
    def _validate_report(data: ReportInput, report: ReportOut) -> None:
        expected = {
            criterion.name: (criterion.score, criterion.weight)
            for criterion in data.matching.criteria
        }
        actual = {
            criterion.name: (criterion.score, criterion.weight) for criterion in report.criteria
        }
        if expected.keys() != actual.keys():
            raise ReportAgentError("Les critères du rapport ne correspondent pas au matching.")
        for name, (score, weight) in expected.items():
            actual_score, actual_weight = actual[name]
            if not math.isclose(actual_score, score, abs_tol=0.01) or not math.isclose(
                actual_weight, weight, abs_tol=0.01
            ):
                raise ReportAgentError(
                    f"Score incohérent pour le critère {name}: "
                    f"attendu {score}/{weight}, reçu {actual_score}/{actual_weight}."
                )
        expected_inconsistencies = {
            f"{item.field}: {item.cv_value} / {item.document_value}"
            for item in data.document_verification.inconsistencies
        }
        if set(report.inconsistencies) != expected_inconsistencies:
            raise ReportAgentError(
                "Les incohérences du rapport ne correspondent pas aux vérifications."
            )
        sensitive_text = " ".join(
            [
                report.conclusion,
                *report.strengths,
                *report.gaps,
                *report.inconsistencies,
                *[criterion.justification for criterion in report.criteria],
            ]
        )
        if _SENSITIVE_PATTERN.search(_normalize_for_scan(sensitive_text)):
            raise ReportAgentError("Le rapport contient une donnée sensible interdite.")

    @staticmethod
    def _with_human_reminder(report: ReportOut) -> ReportOut:
        if _HUMAN_REMINDER.casefold() in report.conclusion.casefold():
            return report
        return report.model_copy(
            update={"conclusion": f"{report.conclusion.rstrip('.')}. {_HUMAN_REMINDER}"}
        )

    @staticmethod
    def candidate_view(data: ReportInput) -> CandidateResultView:
        return build_candidate_view(
            global_score=data.matching.global_score,
            matching_skills=data.matching.matching_skills,
            missing_skills=data.matching.missing_skills,
            compliance_level=data.document_verification.compliance_level,
            has_inconsistencies=bool(data.document_verification.inconsistencies),
        )
