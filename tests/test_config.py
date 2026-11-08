from app.config import Settings


def test_groq_api_key_alias_is_accepted() -> None:
    settings = Settings(
        DATABASE_URL="postgresql+psycopg://user:password@localhost/db",
        SECRET_KEY="local-secret",
        GROQ_API_KEY="test-groq-key",
        _env_file=None,
    )
    assert settings.llm_api_key == "test-groq-key"


def test_legacy_llm_api_key_alias_is_not_used() -> None:
    settings = Settings(
        DATABASE_URL="postgresql+psycopg://user:password@localhost/db",
        SECRET_KEY="local-secret",
        LLM_API_KEY="legacy-key",
        _env_file=None,
    )
    assert settings.llm_api_key is None


def test_groq_configuration_defaults_are_explicit() -> None:
    settings = Settings(
        DATABASE_URL="postgresql://localhost/db",
        SECRET_KEY="local-secret",
        GROQ_API_KEY="test-groq-key",
        _env_file=None,
    )
    assert settings.llm_provider == "groq"
    assert settings.llm_model == "openai/gpt-oss-120b"
    assert settings.llm_base_url == "https://api.groq.com/openai/v1"
