from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, timestamp_column
from app.models.enums import ImportedProfileStatus


class ImportedCandidateProfile(Base):
    """Profil de benchmark importé, sans compte ni candidature métier."""

    __tablename__ = "imported_candidate_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_dataset: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(500), nullable=False)
    extracted_text: Mapped[str | None] = mapped_column(Text)
    professional_category: Mapped[str | None] = mapped_column(String(200), index=True)
    extraction_status: Mapped[ImportedProfileStatus] = mapped_column(
        Enum(
            ImportedProfileStatus,
            name="imported_profile_status",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        default=ImportedProfileStatus.NOT_EXTRACTED,
        nullable=False,
    )
    imported_at: Mapped[datetime] = timestamp_column()
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
