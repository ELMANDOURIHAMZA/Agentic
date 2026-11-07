import logging
import re
import unicodedata
from pathlib import Path

from pydantic import BaseModel, Field

from app.schemas.agent_outputs import (
    DocumentVerificationOut,
    ExtractedProfileOut,
    InconsistencyOut,
)
from app.services.llm import LLMClient, LLMError

logger = logging.getLogger(__name__)
_PROMPT = (Path(__file__).parent / "prompts" / "document_verification_agent.txt").read_text(
    encoding="utf-8"
)
_MASKED = "[masqué]"


class DocumentVerificationInput(BaseModel):
    diploma_text: str | None = Field(default=None, max_length=100_000)
    cin_text: str | None = Field(default=None, max_length=100_000)
    cv_profile: ExtractedProfileOut
    diploma_read_error: str | None = Field(default=None, max_length=300)
    cin_read_error: str | None = Field(default=None, max_length=300)


class VerificationExtractionOut(BaseModel):
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    birth_date: str | None = Field(default=None, max_length=30)
    cin_number: str | None = Field(default=None, max_length=100)
    diploma_title: str | None = Field(default=None, max_length=300)
    institution: str | None = Field(default=None, max_length=300)
    graduation_year: int | None = Field(default=None, ge=1900, le=2100)


class DocumentVerificationAgentError(RuntimeError):
    """Erreur explicite de l'agent de vérification documentaire."""


def _normalized(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", without_accents.casefold()).strip()


def _name_matches(left: str | None, right: str | None) -> bool:
    if not left or not right:
        return False
    return set(_normalized(left).split()) == set(_normalized(right).split())


def _mask_number(value: str | None) -> str:
    if not value:
        return _MASKED
    compact = re.sub(r"\s+", "", value)
    return f"****{compact[-4:]}" if len(compact) >= 4 else _MASKED


def _safe_document_value(value: str | None, sensitive: bool = False) -> str:
    return _MASKED if sensitive and value else (value or "Non renseigné")


def _cv_year(profile: ExtractedProfileOut) -> int | None:
    for value in [*profile.diplomas, *profile.education]:
        match = re.search(r"\b(19\d{2}|20\d{2})\b", value)
        if match:
            return int(match.group(1))
    return None


class DocumentVerificationAgent:
    """Extrait puis compare les justificatifs au CV sans LLM.

    Barème : base 100 ; -50 par justificatif illisible ou vide ; -10 par
    champ non vérifiable ; -30 pour un nom partiellement divergent ; -50 pour
    un nom sans correspondance ; -20 pour une année divergente de moins de
    cinq ans ; -35 au-delà. Le résultat est borné entre 0 et 100.
    """

    def __init__(self, llm_client: LLMClient) -> None:
        self._llm_client = llm_client

    def run(self, data: DocumentVerificationInput) -> DocumentVerificationOut:
        if not data.diploma_text and not data.diploma_read_error:
            data.diploma_read_error = "Document vide."
        if not data.cin_text and not data.cin_read_error:
            data.cin_read_error = "Document vide."
        input_data = (
            "<document_diplome>\n"
            f"{data.diploma_text or '[document indisponible]'}\n"
            "</document_diplome>\n"
            "<document_cin>\n"
            f"{data.cin_text or '[document indisponible]'}\n"
            "</document_cin>"
        )
        try:
            extracted = self._llm_client.generate_structured(
                _PROMPT, input_data, VerificationExtractionOut
            )
        except (LLMError, ValueError, TypeError) as exc:
            logger.error("DocumentVerificationAgent échoué: %s", type(exc).__name__)
            raise DocumentVerificationAgentError(
                "L'extraction des justificatifs a échoué."
            ) from exc
        return self._compare(data, extracted)

    def _compare(
        self, data: DocumentVerificationInput, extracted: VerificationExtractionOut
    ) -> DocumentVerificationOut:
        inconsistencies: list[InconsistencyOut] = []
        compliance = 100.0
        diploma_info = {
            "title": extracted.diploma_title or "",
            "institution": extracted.institution or "",
            "graduation_year": str(extracted.graduation_year or ""),
        }
        cin_info = {
            "first_name": extracted.first_name or "",
            "last_name": extracted.last_name or "",
            "birth_date": _MASKED if extracted.birth_date else "",
            "cin_number": _mask_number(extracted.cin_number),
        }
        if data.diploma_read_error:
            inconsistencies.append(
                InconsistencyOut(
                    field="diplome",
                    cv_value="Non vérifiable",
                    document_value="Document illisible ou vide",
                    severity="low",
                )
            )
            compliance -= 50
        if data.cin_read_error:
            inconsistencies.append(
                InconsistencyOut(
                    field="CIN",
                    cv_value="Non vérifiable",
                    document_value="Document illisible ou vide",
                    severity="low",
                )
            )
            compliance -= 50

        cv_identity = data.cv_profile.declared_identity
        for field, cv_value, document_value in (
            ("prénom", cv_identity.first_name, extracted.first_name),
            ("nom", cv_identity.last_name, extracted.last_name),
        ):
            if not cv_value or not document_value:
                inconsistencies.append(self._missing(field, cv_value, document_value))
                compliance -= 10
            elif not _name_matches(cv_value, document_value):
                severity = (
                    "medium"
                    if set(_normalized(cv_value).split()) & set(_normalized(document_value).split())
                    else "high"
                )
                inconsistencies.append(
                    InconsistencyOut(
                        field=field,
                        cv_value=cv_value,
                        document_value=document_value,
                        severity=severity,
                    )
                )
                compliance -= 30 if severity == "medium" else 50

        cv_year = _cv_year(data.cv_profile)
        if cv_year is None or extracted.graduation_year is None:
            inconsistencies.append(
                self._missing("année de diplôme", cv_year, extracted.graduation_year)
            )
            compliance -= 10
        elif cv_year != extracted.graduation_year:
            gap = abs(cv_year - extracted.graduation_year)
            severity = "high" if gap >= 5 else "medium"
            inconsistencies.append(
                InconsistencyOut(
                    field="année de diplôme",
                    cv_value=str(cv_year),
                    document_value=str(extracted.graduation_year),
                    severity=severity,
                )
            )
            compliance -= 35 if severity == "high" else 20
        return DocumentVerificationOut(
            diploma_info=diploma_info,
            cin_info=cin_info,
            inconsistencies=inconsistencies,
            compliance_level=max(0, compliance),
        )

    @staticmethod
    def _missing(field: str, cv_value: object, document_value: object) -> InconsistencyOut:
        return InconsistencyOut(
            field=field,
            cv_value="Non renseigné" if cv_value is None else str(cv_value),
            document_value="Non renseigné" if document_value is None else str(document_value),
            severity="low",
        )
