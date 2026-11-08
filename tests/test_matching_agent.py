"""Matching Agent : contrat de critères, calcul déterministe, rejets (transport simulé)."""

import json
from typing import Any

import pytest

from app.agents.matching import (
    MatchingAgent,
    MatchingAgentError,
    MatchingInput,
    expected_criteria_ids,
)
from app.schemas.agent_outputs import (
    DocumentVerificationOut,
    ExperienceOut,
    ExtractedProfileOut,
    StructuredRequirementsOut,
)
from app.services.llm import LLMClient
from tests.llm_fakes import FakeLLM, between

PROFILE = ExtractedProfileOut(
    skills=["Python", "FastAPI", "PostgreSQL"],
    diplomas=["Master en informatique"],
    languages=["Anglais", "Français"],
    experiences=[ExperienceOut(position="Dev", employer="X", duration_months=48)],
)
VERIFICATION = DocumentVerificationOut(compliance_level=100)


def requirements(**kwargs: Any) -> StructuredRequirementsOut:
    base: dict[str, Any] = {
        "required_degree": "Master",
        "minimum_experience_years": 2,
        "required_skills": ["Python", "FastAPI"],
        "preferred_skills": ["PostgreSQL"],
        "languages": ["Anglais"],
    }
    base.update(kwargs)
    return StructuredRequirementsOut(**base)


def run(reqs: StructuredRequirementsOut, profile: ExtractedProfileOut = PROFILE, fake=None):
    fake = fake or FakeLLM()
    out = MatchingAgent(LLMClient(transport=fake)).run(
        MatchingInput(requirements=reqs, profile=profile, document_verification=VERIFICATION)
    )
    return out, fake


def verdicts(mapping: dict[str, str]):
    def handler(request: dict[str, Any]) -> dict[str, Any]:
        reqs = StructuredRequirementsOut.model_validate_json(between(request["input"], "exigences"))
        return {
            "criteria": [
                {
                    "name": identifier,
                    "verdict": mapping.get(identifier, "absent"),
                    "justification": "x",
                    "evidence": [
                        "Master en informatique"
                        if identifier == "degree"
                        else identifier.split(":", 1)[-1]
                    ]
                    if mapping.get(identifier, "absent") != "absent"
                    else [],
                }
                for identifier in expected_criteria_ids(reqs)
            ]
        }

    return handler


def test_expected_ids_are_exact_and_deduplicated() -> None:
    ids = expected_criteria_ids(requirements(required_skills=["Python", "Python"]))
    assert ids == [
        "degree",
        "required_skill:Python",
        "preferred_skill:PostgreSQL",
        "language:Anglais",
    ]


def test_request_sent_to_llm_lists_the_expected_criteria(llm_env) -> None:
    _, fake = run(requirements())
    # Le contrat est bien transmis : on rejoue la requête capturée.
    captured: list[dict[str, Any]] = []

    def spy(request: dict[str, Any]) -> dict[str, Any]:
        captured.append(request)
        return FakeLLM.default("SemanticEvaluationOut", request)

    run(requirements(), fake=FakeLLM({"SemanticEvaluationOut": spy}))
    sent = json.loads(between(captured[0]["input"], "criteres_attendus"))
    assert sent == expected_criteria_ids(requirements())
    assert "criteres_attendus" in captured[0]["prompt"]


def test_perfect_candidate_gets_full_score_not_35(llm_env) -> None:
    out, _ = run(requirements())
    assert out.global_score == 100.0
    assert out.missing_skills == []
    assert set(out.matching_skills) == {"Python", "FastAPI", "PostgreSQL", "Anglais"}


def test_candidate_without_any_required_skill(llm_env) -> None:
    profile = PROFILE.model_copy(update={"skills": ["Cobol"]})
    out, _ = run(requirements(), profile)
    details = {c.name: c.score for c in out.criteria}
    assert details["required_skills"] == 0.0
    assert set(out.missing_skills) >= {"Python", "FastAPI"}
    assert out.global_score < 60


def test_candidate_with_partial_skills(llm_env) -> None:
    profile = PROFILE.model_copy(update={"skills": ["Python"]})
    out, _ = run(requirements(), profile)
    details = {c.name: c.score for c in out.criteria}
    assert details["required_skills"] == 50.0
    assert out.matching_skills.count("Python") == 1
    assert "FastAPI" in out.missing_skills


@pytest.mark.parametrize(
    ("verdict", "expected"), [("match", 100.0), ("partiel", 50.0), ("absent", 0.0)]
)
def test_degree_verdicts(llm_env, verdict: str, expected: float) -> None:
    fake = FakeLLM({"SemanticEvaluationOut": verdicts({"degree": verdict})})
    profile = PROFILE.model_copy(update={"diplomas": ["Master en informatique"]})
    out, _ = run(requirements(required_skills=[], preferred_skills=[], languages=[]), profile, fake)
    degree = next(c for c in out.criteria if c.name == "degree")
    assert degree.score == expected


def test_languages_matching_and_missing(llm_env) -> None:
    out, _ = run(requirements(languages=["Anglais", "Allemand"]))
    languages = next(c for c in out.criteria if c.name == "languages")
    assert languages.score == 50.0
    assert "Allemand" in out.missing_skills and "Anglais" in out.matching_skills


def test_missing_criterion_triggers_controlled_retry_then_succeeds(llm_env) -> None:
    attempts: list[int] = []

    def flaky(request: dict[str, Any]) -> dict[str, Any]:
        attempts.append(1)
        full = FakeLLM.default("SemanticEvaluationOut", request)
        if len(attempts) == 1:
            full["criteria"] = full["criteria"][:-1]
        else:
            assert "erreur_validation_precedente" in request["input"]
        return full

    out, _ = run(requirements(), fake=FakeLLM({"SemanticEvaluationOut": flaky}))
    assert len(attempts) == 2 and out.global_score == 100.0


def test_missing_criterion_never_counts_as_silent_absent(llm_env) -> None:
    def always_incomplete(request: dict[str, Any]) -> dict[str, Any]:
        full = FakeLLM.default("SemanticEvaluationOut", request)
        full["criteria"] = full["criteria"][:-1]
        return full

    with pytest.raises(MatchingAgentError):
        run(requirements(), fake=FakeLLM({"SemanticEvaluationOut": always_incomplete}))


def test_invalid_and_duplicate_ids_are_rejected(llm_env) -> None:
    def invalid(request: dict[str, Any]) -> dict[str, Any]:
        full = FakeLLM.default("SemanticEvaluationOut", request)
        full["criteria"][0]["name"] = "Diplôme"
        return full

    def duplicate(request: dict[str, Any]) -> dict[str, Any]:
        full = FakeLLM.default("SemanticEvaluationOut", request)
        full["criteria"].append(dict(full["criteria"][0]))
        return full

    for handler in (invalid, duplicate):
        with pytest.raises(MatchingAgentError):
            run(requirements(), fake=FakeLLM({"SemanticEvaluationOut": handler}))


def test_casing_of_ids_is_tolerated(llm_env) -> None:
    def lowercased(request: dict[str, Any]) -> dict[str, Any]:
        full = FakeLLM.default("SemanticEvaluationOut", request)
        for item in full["criteria"]:
            item["name"] = item["name"].upper()
        return full

    out, _ = run(requirements(), fake=FakeLLM({"SemanticEvaluationOut": lowercased}))
    assert out.global_score == 100.0


def test_malformed_llm_response_is_an_error(llm_env) -> None:
    with pytest.raises(MatchingAgentError):
        run(requirements(), fake=FakeLLM({"SemanticEvaluationOut": "pas du json"}))


def test_unproven_evidence_is_downgraded_with_explanation(llm_env) -> None:
    def invented(request: dict[str, Any]) -> dict[str, Any]:
        full = FakeLLM.default("SemanticEvaluationOut", request)
        for item in full["criteria"]:
            if item["name"] == "required_skill:Python":
                item["evidence"] = ["Expert Rust"]
        return full

    out, _ = run(requirements(), fake=FakeLLM({"SemanticEvaluationOut": invented}))
    skills = next(c for c in out.criteria if c.name == "required_skills")
    assert skills.score == 50.0 and "Python" in out.missing_skills


def test_score_is_deterministic_and_reproducible(llm_env) -> None:
    first, _ = run(requirements())
    second, _ = run(requirements())
    assert first.model_dump() == second.model_dump()


def test_offer_without_degree_excludes_criterion_and_redistributes_weights(llm_env) -> None:
    out, _ = run(requirements(required_degree=""))
    names = [c.name for c in out.criteria]
    assert "degree" not in names
    assert round(sum(c.weight for c in out.criteria), 6) == 100
    assert out.global_score == 100.0
