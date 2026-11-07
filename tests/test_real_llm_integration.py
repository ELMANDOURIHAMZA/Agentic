import os

import pytest

from app.agents.cv_extraction import CVExtractionAgent, CVExtractionInput
from app.agents.document_verification import (
    DocumentVerificationAgent,
    DocumentVerificationInput,
)
from app.agents.job_requirement import JobRequirementAgent, JobRequirementInput
from app.agents.matching import MatchingAgent, MatchingInput
from app.agents.report import ReportAgent, ReportInput
from app.config import get_settings
from app.services.llm import LLMClient

pytestmark = pytest.mark.integration


def _require_real_provider() -> None:
    if os.getenv("RUN_REAL_LLM_TESTS") != "1":
        pytest.skip("Set RUN_REAL_LLM_TESTS=1 to run billable Groq integration tests.")
    settings = get_settings()
    if settings.llm_provider.casefold() != "groq":
        pytest.fail("These integration tests are restricted to Groq.")
    if not (settings.llm_api_key or "").strip():
        pytest.skip("Set GROQ_API_KEY in the environment or local .env file.")


def test_all_agents_use_the_configured_real_provider() -> None:
    _require_real_provider()
    client = LLMClient()
    requirements = JobRequirementAgent(client).run(
        JobRequirementInput(
            title="Python Backend Engineer",
            description="Build APIs with Python and FastAPI. Use PostgreSQL. English required.",
            required_skills=["Python", "FastAPI"],
            languages=["English"],
        )
    )
    profile = CVExtractionAgent(client).run(
        CVExtractionInput(
            cv_text=(
                "Alex Martin. Python backend engineer. "
                "Education: Master in Computer Science, 2021. "
                "Skills: Python, FastAPI, PostgreSQL. English."
            )
        )
    )
    verification = DocumentVerificationAgent(client).run(
        DocumentVerificationInput(
            diploma_text=(
                "Fictional diploma. Holder: Alex Martin. "
                "Title: Master in Computer Science. Graduation year: 2021."
            ),
            cin_text=(
                "Fictional identity document. First name: Alex. Last name: Martin. "
                "Fictional reference: TEST-CIN-00000."
            ),
            cv_profile=profile,
        )
    )
    matching = MatchingAgent(client).run(
        MatchingInput(
            requirements=requirements,
            profile=profile,
            document_verification=verification,
        )
    )
    report = ReportAgent(client).run(
        ReportInput(
            requirements=requirements,
            profile=profile,
            document_verification=verification,
            matching=matching,
        )
    )
    assert report.criteria
    assert 0 <= matching.global_score <= 100
