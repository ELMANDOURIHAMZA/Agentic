from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.enums import ApplicationStatus


class CandidateProfileUpdate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=30)

    @field_validator("first_name", "last_name", "phone")
    @classmethod
    def clean_text(cls, value: str | None) -> str | None:
        cleaned = " ".join(value.split()) if value is not None else None
        return cleaned or None


class CandidateApplicationView(BaseModel):
    id: int
    job_title: str
    applied_at: datetime
    status: ApplicationStatus
    status_label: str


class CandidateResultView(BaseModel):
    global_score: float
    matching_skills: list[str]
    missing_skills: list[str]
    compliance_summary: str


COMPLIANT_SUMMARY = "Dossier conforme."
TO_CONFIRM_SUMMARY = "Vérifications incomplètes : votre dossier sera confirmé par le recruteur."


def build_candidate_view(
    *,
    global_score: float,
    matching_skills: list[str],
    missing_skills: list[str],
    compliance_level: float | None,
    has_inconsistencies: bool,
) -> CandidateResultView:
    """Vue candidat : jamais le détail des incohérences ni le rapport complet."""
    compliant = compliance_level is not None and compliance_level >= 80 and not has_inconsistencies
    return CandidateResultView(
        global_score=global_score,
        matching_skills=[str(value) for value in matching_skills],
        missing_skills=[str(value) for value in missing_skills],
        compliance_summary=COMPLIANT_SUMMARY if compliant else TO_CONFIRM_SUMMARY,
    )
