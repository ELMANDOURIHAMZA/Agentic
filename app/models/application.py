from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, timestamp_column
from app.models.enums import ApplicationStatus

if TYPE_CHECKING:
    from app.models.analysis import AnalysisResult, DocumentVerification, ExtractedProfile
    from app.models.document import Document
    from app.models.user import User
    from app.models.workflow import WorkflowRun


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (
        UniqueConstraint("candidate_id", "job_id", name="uq_applications_candidate_job"),
        Index("ix_applications_status", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    applied_at: Mapped[datetime] = timestamp_column()
    status: Mapped[ApplicationStatus] = mapped_column(
        Enum(
            ApplicationStatus,
            name="application_status",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        default=ApplicationStatus.SUBMITTED,
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    candidate: Mapped["User"] = relationship(back_populates="applications")
    documents: Mapped[list["Document"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )
    extracted_profile: Mapped["ExtractedProfile | None"] = relationship(
        back_populates="application", cascade="all, delete-orphan", uselist=False
    )
    document_verification: Mapped["DocumentVerification | None"] = relationship(
        back_populates="application", cascade="all, delete-orphan", uselist=False
    )
    analysis_result: Mapped["AnalysisResult | None"] = relationship(
        back_populates="application", cascade="all, delete-orphan", uselist=False
    )
    workflow_runs: Mapped[list["WorkflowRun"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )
