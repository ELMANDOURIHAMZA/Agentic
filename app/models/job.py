from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, Enum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, timestamp_column, updated_column
from app.models.enums import JobStatus

if TYPE_CHECKING:
    from app.models.analysis import StructuredRequirements


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    required_degree: Mapped[str | None] = mapped_column(String(200))
    required_experience_years: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    required_skills: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)
    preferred_skills: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)
    required_certifications: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)
    languages: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)
    other_requirements: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[JobStatus] = mapped_column(
        Enum(
            JobStatus,
            name="job_status",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        default=JobStatus.DRAFT,
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = timestamp_column()
    updated_at: Mapped[datetime] = updated_column()
    published_at: Mapped[datetime | None] = mapped_column()
    closed_at: Mapped[datetime | None] = mapped_column()
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    is_template: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    structured_requirements: Mapped["StructuredRequirements | None"] = relationship(
        back_populates="job", cascade="all, delete-orphan", uselist=False
    )
