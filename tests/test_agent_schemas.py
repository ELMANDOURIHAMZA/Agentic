import pytest
from pydantic import ValidationError

from app.agents.cv_extraction import CVExtractionInput
from app.agents.job_requirement import JobRequirementInput
from app.schemas.agent_outputs import ExtractedProfileOut, StructuredRequirementsOut


def test_job_requirements_support_certifications_and_other_requirements() -> None:
    result = StructuredRequirementsOut(
        required_degree="Master",
        minimum_experience_years=3,
        required_certifications=["AWS"],
        other_requirements="Astreinte occasionnelle",
    )
    assert result.required_certifications == ["AWS"]
    assert result.other_requirements == "Astreinte occasionnelle"


def test_cv_profile_supports_projects_and_contributions() -> None:
    result = ExtractedProfileOut(
        projects=[
            {
                "name": "API interne",
                "description": "API de suivi",
                "technologies": ["Python", "FastAPI"],
            }
        ],
        professional_contributions=["Revue de code"],
    )
    assert result.projects[0].technologies == ["Python", "FastAPI"]
    assert result.professional_contributions == ["Revue de code"]


def test_agent_inputs_reject_empty_required_values() -> None:
    with pytest.raises(ValidationError):
        JobRequirementInput(title="")
    with pytest.raises(ValidationError):
        CVExtractionInput(cv_text="")


def test_job_without_required_degree_is_valid() -> None:
    result = StructuredRequirementsOut(
        required_degree="",
        minimum_experience_years=0,
    )
    assert result.required_degree == ""
