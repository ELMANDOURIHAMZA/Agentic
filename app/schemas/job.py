from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import JobStatus


def clean_list(value: list[str] | None) -> list[str]:
    if not value:
        return []
    cleaned: list[str] = []
    for item in value:
        normalized = " ".join(item.split())
        if normalized and normalized.casefold() not in {entry.casefold() for entry in cleaned}:
            cleaned.append(normalized)
    return cleaned


class JobFields(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=10, max_length=10_000)
    required_degree: str | None = Field(default=None, max_length=200)
    required_experience_years: int = Field(default=0, ge=0, le=60)
    required_skills: list[str] = Field(default_factory=list, max_length=100)
    preferred_skills: list[str] = Field(default_factory=list, max_length=100)
    required_certifications: list[str] = Field(default_factory=list, max_length=50)
    languages: list[str] = Field(default_factory=list, max_length=30)
    location: str | None = Field(default=None, max_length=200)
    other_requirements: str | None = Field(default=None, max_length=5_000)

    @field_validator("required_skills", "preferred_skills", "required_certifications", "languages")
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return clean_list(value)

    @field_validator("title", "description", "required_degree", "location", "other_requirements")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        return " ".join(value.split()) if value is not None else None


class JobCreate(JobFields):
    pass


class JobUpdate(JobFields):
    pass


class JobRead(JobFields):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None
    closed_at: datetime | None
