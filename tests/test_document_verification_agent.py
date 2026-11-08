"""Document Verification Agent : extraction simulée + comparaison déterministe."""

from typing import Any

from app.agents.document_verification import DocumentVerificationAgent, DocumentVerificationInput
from app.schemas.agent_outputs import DeclaredIdentityOut, ExtractedProfileOut
from app.services.llm import LLMClient
from tests.llm_fakes import FakeLLM

PROFILE = ExtractedProfileOut(
    education=["Master en informatique, Université Atlas, 2020"],
    diplomas=["Master en informatique 2020"],
    declared_identity=DeclaredIdentityOut(first_name="Amina", last_name="Benali"),
)


def verify(extraction: dict[str, Any] | None = None, **kwargs: Any):
    base = FakeLLM.default("VerificationExtractionOut", {"input": ""})
    base.update(extraction or {})
    fake = FakeLLM({"VerificationExtractionOut": lambda _r: base})
    data = DocumentVerificationInput(
        diploma_text=kwargs.pop("diploma_text", "texte diplôme"),
        cin_text=kwargs.pop("cin_text", "texte cin"),
        cv_profile=kwargs.pop("profile", PROFILE),
        **kwargs,
    )
    return DocumentVerificationAgent(LLMClient(transport=fake)).run(data)


def kinds(result) -> set[str]:
    return {item.kind for item in result.inconsistencies}


def test_consistent_dossier_is_fully_compliant(llm_env) -> None:
    result = verify()
    assert result.compliance_level == 100 and result.inconsistencies == []


def test_cin_number_is_masked_and_birth_date_hidden(llm_env) -> None:
    result = verify({"cin_number": "ZZ123456", "birth_date": "01/01/1990"})
    assert result.cin_info["cin_number"] == "****3456"
    assert result.cin_info["birth_date"] == "[masqué]"
    assert "ZZ123456" not in result.model_dump_json()


def test_diploma_belonging_to_someone_else_is_detected(llm_env) -> None:
    result = verify({"diploma_holder_first_name": "Karim", "diploma_holder_last_name": "Idrissi"})
    item = next(i for i in result.inconsistencies if i.kind == "diploma_holder")
    assert item.severity == "high" and "autre personne" in item.explanation
    assert result.compliance_level <= 50


def test_identity_mismatch_cin_vs_cv(llm_env) -> None:
    result = verify({"last_name": "Alaoui"})
    item = next(i for i in result.inconsistencies if i.kind == "identity")
    assert item.field == "nom" and item.severity == "high"


def test_partial_name_match_is_medium(llm_env) -> None:
    result = verify({"diploma_holder_first_name": "Amina", "diploma_holder_last_name": "Alaoui"})
    item = next(i for i in result.inconsistencies if i.kind == "diploma_holder")
    assert item.severity == "medium"


def test_diploma_title_inconsistent(llm_env) -> None:
    result = verify({"diploma_title": "Doctorat en médecine vétérinaire"})
    item = next(i for i in result.inconsistencies if i.kind == "diploma_title")
    assert item.severity == "medium"


def test_year_contradiction(llm_env) -> None:
    result = verify({"graduation_year": 2012})
    item = next(i for i in result.inconsistencies if i.kind == "year")
    assert item.severity == "high"


def test_missing_information_is_low_and_not_fraud(llm_env) -> None:
    result = verify(
        {"institution": None, "diploma_holder_first_name": None, "diploma_holder_last_name": None}
    )
    item = next(i for i in result.inconsistencies if i.field == "titulaire du diplôme")
    assert item.severity == "low" and "pas une preuve de fraude" in item.explanation


def test_unreadable_document_is_flagged_without_other_false_alarms(llm_env) -> None:
    result = verify(diploma_text=None, diploma_read_error="Document illisible ou introuvable.")
    assert kinds(result) == {"unreadable"}
    assert result.inconsistencies[0].severity == "low"
    assert result.compliance_level == 50


def test_accents_and_name_order_are_normalized(llm_env) -> None:
    result = verify({"diploma_holder_first_name": "BENALI", "diploma_holder_last_name": "aména"})
    assert result.inconsistencies and kinds(result) <= {"diploma_holder"}
    result = verify({"diploma_holder_first_name": "Benali", "diploma_holder_last_name": "Amina"})
    assert result.inconsistencies == []
