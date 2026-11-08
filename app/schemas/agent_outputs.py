from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Severity = Literal["low", "medium", "high"]
InconsistencyKind = Literal[
    "identity",  # nom/prénom CIN ≠ CV
    "diploma_holder",  # titulaire du diplôme ≠ identité du candidat
    "diploma_title",  # intitulé du diplôme ≠ CV
    "year",  # année contradictoire
    "institution",  # établissement absent du CV
    "missing",  # information absente (pas une preuve de fraude)
    "unreadable",  # document illisible ou extraction incertaine (pas une preuve de fraude)
]


def _clean_list(values: list[str]) -> list[str]:
    cleaned = [" ".join(value.split()) for value in values]
    return list(dict.fromkeys(value for value in cleaned if value))


class StructuredRequirementsOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    required_degree: str = Field(default="", max_length=300)
    minimum_experience_years: float = Field(default=0, ge=0, le=80)
    required_skills: list[str] = Field(default_factory=list, max_length=100)
    preferred_skills: list[str] = Field(default_factory=list, max_length=100)
    required_certifications: list[str] = Field(default_factory=list, max_length=50)
    languages: list[str] = Field(default_factory=list, max_length=30)
    other_requirements: str = Field(default="", max_length=5000)

    @field_validator("required_skills", "preferred_skills", "required_certifications", "languages")
    @classmethod
    def clean_lists(cls, values: list[str]) -> list[str]:
        if any(len(value) > 100 for value in values):
            raise ValueError("Chaque élément doit contenir au plus 100 caractères.")
        return _clean_list(values)


class ExperienceOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    position: str = Field(min_length=1, max_length=200)
    employer: str = Field(min_length=1, max_length=200)
    duration_months: int = Field(ge=0, le=960)


class ProjectOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)
    technologies: list[str] = Field(default_factory=list, max_length=50)

    @field_validator("technologies")
    @classmethod
    def clean_technologies(cls, values: list[str]) -> list[str]:
        return _clean_list(values)


class DeclaredIdentityOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    birth_date: date | None = None


class ExtractedProfileOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    education: list[str] = Field(default_factory=list, max_length=50)
    diplomas: list[str] = Field(default_factory=list, max_length=50)
    experiences: list[ExperienceOut] = Field(default_factory=list, max_length=50)
    projects: list[ProjectOut] = Field(default_factory=list, max_length=50)
    skills: list[str] = Field(default_factory=list, max_length=100)
    certifications: list[str] = Field(default_factory=list, max_length=50)
    professional_contributions: list[str] = Field(default_factory=list, max_length=50)
    languages: list[str] = Field(default_factory=list, max_length=30)
    declared_identity: DeclaredIdentityOut = Field(default_factory=DeclaredIdentityOut)

    @field_validator(
        "education",
        "diplomas",
        "skills",
        "certifications",
        "professional_contributions",
        "languages",
    )
    @classmethod
    def clean_lists(cls, values: list[str]) -> list[str]:
        if any(len(value) > 200 for value in values):
            raise ValueError("Chaque élément doit contenir au plus 200 caractères.")
        return _clean_list(values)


class InconsistencyOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str = Field(min_length=1, max_length=100)
    cv_value: str = Field(max_length=500)
    document_value: str = Field(max_length=500)
    severity: Severity
    kind: InconsistencyKind = "identity"
    explanation: str = Field(default="", max_length=500)


class DocumentVerificationOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    diploma_info: dict[str, str] = Field(default_factory=dict, max_length=30)
    cin_info: dict[str, str] = Field(default_factory=dict, max_length=30)
    inconsistencies: list[InconsistencyOut] = Field(default_factory=list, max_length=100)
    compliance_level: float = Field(ge=0, le=100)


class MatchingCriterionOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    score: float = Field(ge=0, le=100)
    weight: float = Field(ge=0, le=100)
    justification: str = Field(min_length=1, max_length=1000)
    evidence: list[str] = Field(default_factory=list, max_length=50)


class MatchingOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    global_score: float = Field(ge=0, le=100)
    criteria: list[MatchingCriterionOut] = Field(default_factory=list, max_length=50)
    matching_skills: list[str] = Field(default_factory=list, max_length=100)
    missing_skills: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("matching_skills", "missing_skills")
    @classmethod
    def clean_lists(cls, values: list[str]) -> list[str]:
        if any(len(value) > 200 for value in values):
            raise ValueError("Chaque compétence doit contenir au plus 200 caractères.")
        return _clean_list(values)


class ReportOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    class Criterion(BaseModel):
        model_config = ConfigDict(extra="forbid")

        name: str = Field(min_length=1, max_length=100)
        score: float = Field(ge=0, le=100)
        weight: float = Field(ge=0, le=100)
        justification: str = Field(min_length=1, max_length=1000)
        evidence: list[str] = Field(default_factory=list, max_length=50)

    strengths: list[str] = Field(default_factory=list, max_length=50)
    gaps: list[str] = Field(default_factory=list, max_length=50)
    inconsistencies: list[str] = Field(default_factory=list, max_length=50)
    criteria: list[Criterion] = Field(default_factory=list, max_length=50)
    conclusion: str = Field(min_length=1, max_length=2000)
    human_decision_reminder: str = Field(
        default="La décision finale appartient à un humain.",
        min_length=1,
        max_length=300,
    )

    @field_validator("strengths", "gaps", "inconsistencies")
    @classmethod
    def clean_lists(cls, values: list[str]) -> list[str]:
        if any(len(value) > 500 for value in values):
            raise ValueError("Chaque élément doit contenir au plus 500 caractères.")
        return _clean_list(values)
