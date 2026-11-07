from app.agents.matching import MatchingAgent, MatchingInput
from app.agents.report import ReportAgent, ReportInput
from app.schemas.agent_outputs import (
    DocumentVerificationOut,
    ExtractedProfileOut,
    InconsistencyOut,
    MatchingOut,
    ReportOut,
    StructuredRequirementsOut,
)


class RecordingLLM:
    def __init__(self) -> None:
        self.requests: list[str] = []

    def generate_structured(self, prompt, input_data, schema):
        self.requests.append(str(input_data))
        if schema.__name__ == "SemanticEvaluationOut":
            return schema(criteria=[])
        if schema is ReportOut:
            return ReportOut(conclusion="Rapport factuel et neutre.")
        raise AssertionError(f"Unexpected schema: {schema.__name__}")


def _sensitive_test_data():
    requirements = StructuredRequirementsOut(
        required_degree="",
        minimum_experience_years=0,
    )
    profile = ExtractedProfileOut(
        education=["Master informatique 2022"],
        diplomas=["Master informatique 2022"],
        declared_identity={
            "first_name": "Nadia",
            "last_name": "Bennani",
            "birth_date": "1998-04-12",
        },
    )
    verification = DocumentVerificationOut(
        diploma_info={
            "holder_first_name": "Meriem",
            "holder_last_name": "Bennani",
            "title": "Master informatique",
        },
        cin_info={
            "first_name": "Nadia",
            "last_name": "Bennani",
            "birth_date": "[masqué]",
            "cin_number": "****1234",
        },
        inconsistencies=[
            InconsistencyOut(
                field="prénom du titulaire du diplôme",
                cv_value="Nadia",
                document_value="Meriem",
                severity="high",
            )
        ],
        compliance_level=50,
    )
    return requirements, profile, verification


def test_matching_llm_receives_no_candidate_identity() -> None:
    requirements, profile, verification = _sensitive_test_data()
    llm = RecordingLLM()

    MatchingAgent(llm).run(
        MatchingInput(
            requirements=requirements,
            profile=profile,
            document_verification=verification,
        )
    )

    request = llm.requests[0]
    for value in ("Nadia", "Bennani", "Meriem", "1998-04-12", "1234"):
        assert value not in request
    assert '"compliance_level": 50' in request


def test_report_llm_receives_redacted_identity_but_admin_report_keeps_inconsistency() -> None:
    requirements, profile, verification = _sensitive_test_data()
    llm = RecordingLLM()
    matching = MatchingOut(global_score=50, criteria=[])

    report = ReportAgent(llm).run(
        ReportInput(
            requirements=requirements,
            profile=profile,
            document_verification=verification,
            matching=matching,
        )
    )

    request = llm.requests[0]
    for value in ("Nadia", "Bennani", "Meriem", "1998-04-12", "1234"):
        assert value not in request
    assert "[identité masquée]" in request
    assert any("Nadia / Meriem" in item for item in report.inconsistencies)
