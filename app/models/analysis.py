from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Float, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, timestamp_column

if TYPE_CHECKING:
    from app.models.application import Application
    from app.models.job import Job


class StructuredRequirements(Base):
    __tablename__ = "structured_requirements"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = timestamp_column()
    job: Mapped["Job"] = relationship(back_populates="structured_requirements")


class ExtractedProfile(Base):
    __tablename__ = "extracted_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = timestamp_column()
    application: Mapped["Application"] = relationship(back_populates="extracted_profile")


class DocumentVerification(Base):
    __tablename__ = "document_verifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = timestamp_column()
    application: Mapped["Application"] = relationship(back_populates="document_verification")


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    global_score: Mapped[float] = mapped_column(Float, nullable=False)
    score_details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    matching_skills: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)
    missing_skills: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)
    report: Mapped[str] = mapped_column(Text, nullable=False)
    analyzed_at: Mapped[datetime] = timestamp_column()
    application: Mapped["Application"] = relationship(back_populates="analysis_result")
