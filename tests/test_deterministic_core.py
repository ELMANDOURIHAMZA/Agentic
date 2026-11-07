from app.agents.matching import _norm, validate_matching_weights
from app.agents.normalization import normalize_skills


def test_matching_weights_are_deterministic() -> None:
    validate_matching_weights(
        {
            "required_skills": 40,
            "experience": 20,
            "degree": 15,
            "preferred_skills": 10,
            "languages": 5,
            "documents": 10,
        }
    )


def test_multilingual_normalization_is_stable() -> None:
    assert _norm("Développeur Python") == "developpeur python"
    assert _norm("أحمد") == "احمد"


def test_skill_normalization_deduplicates_aliases() -> None:
    assert normalize_skills([" JS ", "JavaScript", "Postgres", "PostgreSQL"]) == [
        "JavaScript",
        "PostgreSQL",
    ]
