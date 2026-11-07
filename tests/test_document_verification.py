from app.agents.document_verification import (
    DocumentVerificationAgent,
    DocumentVerificationInput,
    VerificationExtractionOut,
    _name_matches,
)
from app.schemas.agent_outputs import ExtractedProfileOut
from app.services.llm import LLMClient


def test_arabic_names_are_normalized_without_deleting_arabic_letters() -> None:
    assert _name_matches("أحمد", "احمد")
    assert _name_matches("مُحَمَّد", "محمد")
    assert not _name_matches("أحمد", "علي")


def test_document_verification_flags_diploma_holder_mismatch() -> None:
    profile = ExtractedProfileOut(
        diplomas=["Master informatique 2022"],
        education=["Université fictive — 2022"],
        declared_identity={"first_name": "Sarah", "last_name": "Bennani"},
    )
    input_data = DocumentVerificationInput(
        diploma_text="Diplôme fictif",
        cin_text="CIN fictive",
        cv_profile=profile,
    )
    extracted = VerificationExtractionOut(
        first_name="Sarah",
        last_name="Bennani",
        diploma_first_name="Samira",
        diploma_last_name="Bennani",
        diploma_title="Master informatique",
        institution="Université fictive",
        graduation_year=2022,
    )

    result = DocumentVerificationAgent(LLMClient())._compare(input_data, extracted)

    assert any(
        item.field == "prénom du titulaire du diplôme" and item.severity == "high"
        for item in result.inconsistencies
    )
    assert result.compliance_level == 50


def test_document_verification_keeps_matching_arabic_identity() -> None:
    profile = ExtractedProfileOut(
        diplomas=["Master 2022"],
        declared_identity={"first_name": "أحمد", "last_name": "العلوي"},
    )
    input_data = DocumentVerificationInput(
        diploma_text="Diplôme fictif",
        cin_text="CIN fictive",
        cv_profile=profile,
    )
    extracted = VerificationExtractionOut(
        first_name="احمد",
        last_name="العلوي",
        diploma_first_name="أحمد",
        diploma_last_name="العلوي",
        diploma_title="Master",
        institution="Université fictive",
        graduation_year=2022,
    )

    result = DocumentVerificationAgent(LLMClient())._compare(input_data, extracted)

    assert result.inconsistencies == []
    assert result.compliance_level == 100


def test_diploma_surname_is_still_checked_when_first_name_is_missing() -> None:
    profile = ExtractedProfileOut(
        diplomas=["Master 2022"],
        declared_identity={"first_name": "Sarah", "last_name": "Bennani"},
    )
    input_data = DocumentVerificationInput(
        diploma_text="Diplôme fictif",
        cin_text="CIN fictive",
        cv_profile=profile,
    )
    extracted = VerificationExtractionOut(
        first_name="Sarah",
        last_name="Bennani",
        diploma_first_name=None,
        diploma_last_name="El Amrani",
        diploma_title="Master",
        institution="Université fictive",
        graduation_year=2022,
    )

    result = DocumentVerificationAgent(LLMClient())._compare(input_data, extracted)

    assert any(
        item.field == "nom du titulaire du diplôme" and item.severity == "high"
        for item in result.inconsistencies
    )
