from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = Field(validation_alias="DATABASE_URL")
    secret_key: str = Field(validation_alias="SECRET_KEY")
    postgres_password: str = Field(default="change-me", validation_alias="POSTGRES_PASSWORD")
    llm_provider: str = Field(default="groq", validation_alias="LLM_PROVIDER")
    llm_api_key: str | None = Field(default=None, validation_alias="GROQ_API_KEY")
    llm_model: str | None = Field(default=None, validation_alias="LLM_MODEL")
    ocr_languages: str = Field(default="fra+eng+ara", validation_alias="OCR_LANGUAGES")
    llm_base_url: str | None = Field(default=None, validation_alias="LLM_BASE_URL")
    llm_timeout_seconds: float = Field(
        default=30.0, gt=0, le=300, validation_alias="LLM_TIMEOUT_SECONDS"
    )
    llm_max_retries: int = Field(default=2, ge=0, le=2, validation_alias="LLM_MAX_RETRIES")
    llm_retry_backoff_seconds: float = Field(
        default=5.0, gt=0, le=60, validation_alias="LLM_RETRY_BACKOFF_SECONDS"
    )
    workflow_stale_timeout_seconds: int = Field(
        default=3600, gt=0, le=86400, validation_alias="WORKFLOW_STALE_TIMEOUT_SECONDS"
    )
    matching_required_skills_weight: float = Field(
        default=40, ge=0, le=100, validation_alias="MATCHING_REQUIRED_SKILLS_WEIGHT"
    )
    matching_experience_weight: float = Field(
        default=20, ge=0, le=100, validation_alias="MATCHING_EXPERIENCE_WEIGHT"
    )
    matching_degree_weight: float = Field(
        default=15, ge=0, le=100, validation_alias="MATCHING_DEGREE_WEIGHT"
    )
    matching_preferred_skills_weight: float = Field(
        default=10, ge=0, le=100, validation_alias="MATCHING_PREFERRED_SKILLS_WEIGHT"
    )
    matching_languages_weight: float = Field(
        default=5, ge=0, le=100, validation_alias="MATCHING_LANGUAGES_WEIGHT"
    )
    matching_documents_weight: float = Field(
        default=10, ge=0, le=100, validation_alias="MATCHING_DOCUMENTS_WEIGHT"
    )
    smtp_host: str = Field(default="localhost", validation_alias="SMTP_HOST")
    smtp_port: int = Field(default=1025, validation_alias="SMTP_PORT")
    smtp_user: str | None = Field(default=None, validation_alias="SMTP_USER")
    smtp_password: str | None = Field(default=None, validation_alias="SMTP_PASSWORD")
    smtp_starttls: bool = Field(default=True, validation_alias="SMTP_STARTTLS")
    admin_notification_email: str = Field(
        default="admin@example.test", validation_alias="ADMIN_NOTIFICATION_EMAIL"
    )
    upload_dir: str = Field(default="uploads", validation_alias="UPLOAD_DIR")
    max_upload_mb: int = Field(default=10, validation_alias="MAX_UPLOAD_MB")
    app_env: str = Field(default="development", validation_alias="APP_ENV")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def reject_default_secret_outside_development(self) -> "Settings":
        default_secret = "replace-with-a-local-development-secret"
        if self.app_env != "development":
            if self.secret_key == default_secret:
                raise ValueError("SECRET_KEY must be changed outside development")
            if self.postgres_password == "change-me":
                raise ValueError("POSTGRES_PASSWORD must be changed outside development")
        return self

    @model_validator(mode="after")
    def validate_matching_weights(self) -> "Settings":
        weights = (
            self.matching_required_skills_weight,
            self.matching_experience_weight,
            self.matching_degree_weight,
            self.matching_preferred_skills_weight,
            self.matching_languages_weight,
            self.matching_documents_weight,
        )
        if round(sum(weights), 6) != 100:
            raise ValueError("Les pondérations du matching doivent totaliser 100")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
