from typing import Any

from app.agents.job_requirement import JobRequirementAgent, JobRequirementInput
from app.services.llm import LLMClient
from tests.llm_fakes import FakeLLM


def agent_output(request: dict[str, Any]) -> dict[str, Any]:
    return {"required_degree": "", "minimum_experience_years": 0, "required_skills": ["python"]}


def test_offer_without_degree_is_accepted_and_no_degree_is_invented(llm_env) -> None:
    fake = FakeLLM({"StructuredRequirementsOut": agent_output})
    out = JobRequirementAgent(LLMClient(transport=fake)).run(
        JobRequirementInput(
            title="Dev Python", description="Backend Python", required_skills=["Python"]
        )
    )
    assert out.required_degree == ""
    assert out.required_skills == ["Python"]


def test_offer_with_degree_keeps_admin_degree(llm_env) -> None:
    fake = FakeLLM({"StructuredRequirementsOut": lambda r: {"required_degree": "Doctorat"}})
    out = JobRequirementAgent(LLMClient(transport=fake)).run(
        JobRequirementInput(
            title="Dev", description="d", required_degree="Master", minimum_experience_years=3
        )
    )
    assert out.required_degree == "Master" and out.minimum_experience_years == 3


def test_output_without_optional_fields_is_valid(llm_env) -> None:
    fake = FakeLLM({"StructuredRequirementsOut": "{}"})
    out = JobRequirementAgent(LLMClient(transport=fake)).run(
        JobRequirementInput(title="Dev", description="d")
    )
    assert out.required_degree == ""
