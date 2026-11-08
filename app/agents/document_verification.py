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
    # Identité lue sur la CIN
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    birth_date: str | None = Field(default=None, max_length=30)
    cin_number: str | None = Field(default=None, max_length=100)
    # Titulaire lu sur le diplôme
    diploma_holder_first_name: str | None = Field(default=None, max_length=100)
    diploma_holder_last_name: str | None = Field(default=None, max_length=100)
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


_STOPWORDS = {"de", "du", "des", "la", "le", "les", "en", "et", "of", "in", "and", "the", "d", "l"}


def _significant(value: str) -> set[str]:
    return {t for t in _normalized(value).split() if len(t) > 2 and t not in _STOPWORDS}


def _cv_year(profile: ExtractedProfileOut) -> int | None:
    for value in [*profile.diplomas, *profile.education]:
        match = re.search(r"\b(19\d{2}|20\d{2})\b", value)
        if match:
            return int(match.group(1))
    return None


class DocumentVerificationAgent:
    """Extrait puis compare les justificatifs au CV sans LLM.

    Barème : base 100 ; -50 par justificatif illisible ou vide ; -10 par
    champ non vérifiable ; identité CIN↔CV et titulaire du diplôme↔candidat :
    -30 si correspondance partielle, -50 sans correspondance ; intitulé du
    diplôme↔CV : -10 (partiel) ou -20 (aucun mot en commun) ; année divergente :
    -20 (< 5 ans) ou -35 (≥ 5 ans). Une information absente ou illisible est
    signalée en gravité « faible » et n'est jamais présentée comme une fraude.
    Le résultat est borné entre 0 et 100.
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
        holder_name = " ".join(
            part
            for part in (extracted.diploma_holder_first_name, extracted.diploma_holder_last_name)
            if part
        )
        diploma_info = {
            "holder": holder_name,
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
        for read_error, field, label in (
            (data.diploma_read_error, "diplome", "diplôme"),
            (data.cin_read_error, "CIN", "CIN"),
        ):
            if read_error:
                inconsistencies.append(
                    InconsistencyOut(
                        field=field,
                        cv_value="Non vérifiable",
                        document_value="Document illisible ou vide",
                        severity="low",
                        kind="unreadable",
                        explanation=(
                            f"Le document {label} n'a pas pu être lu : cela ne prouve aucune "
                            "fraude, une revue manuelle est nécessaire."
                        ),
                    )
                )
                compliance -= 50

        cv_identity = data.cv_profile.declared_identity
        # 1) Identité CIN ↔ CV
        if not data.cin_read_error:
            for field, cv_value, document_value in (
                ("prénom", cv_identity.first_name, extracted.first_name),
                ("nom", cv_identity.last_name, extracted.last_name),
            ):
                if not cv_value or not document_value:
                    inconsistencies.append(
                        self._missing(field, cv_value, document_value, "CIN ou CV")
                    )
                    compliance -= 10
                elif not _name_matches(cv_value, document_value):
                    shared = set(_normalized(cv_value).split()) & set(
                        _normalized(document_value).split()
                    )
                    severity = "medium" if shared else "high"
                    inconsistencies.append(
                        InconsistencyOut(
                            field=field,
                            cv_value=cv_value,
                            document_value=document_value,
                            severity=severity,
                            kind="identity",
                            explanation=(
                                f"Le {field} lu sur la CIN diffère de celui déclaré dans le CV"
                                + (" (correspondance partielle)." if shared else ".")
                            ),
                        )
                    )
                    compliance -= 30 if severity == "medium" else 50

        # 2) Titulaire du diplôme ↔ identité du candidat
        if not data.diploma_read_error:
            compliance -= self._compare_holder(inconsistencies, holder_name, data, extracted)
            # 3) Intitulé du diplôme ↔ CV
            compliance -= self._compare_title(inconsistencies, data, extracted)

        # 4) Année du diplôme
        cv_year = _cv_year(data.cv_profile)
        if not data.diploma_read_error:
            if cv_year is None or extracted.graduation_year is None:
                inconsistencies.append(
                    self._missing(
                        "année de diplôme", cv_year, extracted.graduation_year, "diplôme ou CV"
                    )
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
                        kind="year",
                        explanation=f"Écart de {gap} an(s) entre le CV et le diplôme.",
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
    def _compare_holder(
        inconsistencies: list[InconsistencyOut],
        holder_name: str,
        data: DocumentVerificationInput,
        extracted: VerificationExtractionOut,
    ) -> float:
        identity = data.cv_profile.declared_identity
        reference = " ".join(part for part in (identity.first_name, identity.last_name) if part)
        reference = reference or " ".join(
            part for part in (extracted.first_name, extracted.last_name) if part
        )
        if not holder_name or not reference:
            inconsistencies.append(
                InconsistencyOut(
                    field="titulaire du diplôme",
                    cv_value=reference or "Non renseigné",
                    document_value=holder_name or "Non renseigné",
                    severity="low",
                    kind="missing",
                    explanation=(
                        "Titulaire du diplôme ou identité du candidat non lisible : "
                        "vérification impossible (absence d'information, pas une preuve de fraude)."
                    ),
                )
            )
            return 10
        if _name_matches(holder_name, reference):
            return 0
        shared = set(_normalized(holder_name).split()) & set(_normalized(reference).split())
        severity = "medium" if shared else "high"
        inconsistencies.append(
            InconsistencyOut(
                field="titulaire du diplôme",
                cv_value=reference,
                document_value=holder_name,
                severity=severity,
                kind="diploma_holder",
                explanation=(
                    "Le nom du titulaire du diplôme ne correspond pas au candidat : "
                    "le diplôme pourrait appartenir à une autre personne (à confirmer)."
                    if not shared
                    else "Le nom du titulaire du diplôme ne correspond que partiellement."
                ),
            )
        )
        return 30 if shared else 50

    @staticmethod
    def _compare_title(
        inconsistencies: list[InconsistencyOut],
        data: DocumentVerificationInput,
        extracted: VerificationExtractionOut,
    ) -> float:
        entries = [*data.cv_profile.diplomas, *data.cv_profile.education]
        title = extracted.diploma_title
        if not title or not entries:
            inconsistencies.append(
                InconsistencyOut(
                    field="intitulé du diplôme",
                    cv_value="; ".join(entries[:2]) or "Non renseigné",
                    document_value=title or "Non renseigné",
                    severity="low",
                    kind="missing",
                    explanation="Intitulé non lisible ou absent du CV : comparaison impossible.",
                )
            )
            return 10
        wanted = _significant(title)
        best = max(
            (len(wanted & _significant(entry)) / len(wanted) for entry in entries), default=0
        )
        if not wanted or best >= 0.5:
            return 0
        severity, penalty = ("low", 10) if best > 0 else ("medium", 20)
        inconsistencies.append(
            InconsistencyOut(
                field="intitulé du diplôme",
                cv_value="; ".join(entries[:2]),
                document_value=title,
                severity=severity,
                kind="diploma_title",
                explanation=(
                    "Intitulé du diplôme partiellement cohérent avec le CV."
                    if best > 0
                    else "Aucun mot significatif de l'intitulé du diplôme ne figure dans le CV."
                ),
            )
        )
        return penalty

    @staticmethod
    def _missing(
        field: str, cv_value: object, document_value: object, source: str = "document"
    ) -> InconsistencyOut:
        return InconsistencyOut(
            field=field,
            cv_value="Non renseigné" if not cv_value else str(cv_value),
            document_value="Non renseigné" if not document_value else str(document_value),
            severity="low",
            kind="missing",
            explanation=(
                f"Information absente ou illisible ({source}) : vérification impossible, "
                "ce qui ne constitue pas une preuve de fraude."
            ),
        )
