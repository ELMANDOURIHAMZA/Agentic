from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, timestamp_column
from app.models.enums import WorkflowStatus

if TYPE_CHECKING:
    from app.models.application import Application


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[WorkflowStatus] = mapped_column(
        Enum(
            WorkflowStatus,
            name="workflow_status",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        default=WorkflowStatus.PENDING,
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column()
    finished_at: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime] = timestamp_column()
    application: Mapped["Application"] = relationship(back_populates="workflow_runs")
    steps: Mapped[list["WorkflowStepLog"]] = relationship(
        back_populates="workflow_run", cascade="all, delete-orphan"
    )


class WorkflowStepLog(Base):
    __tablename__ = "workflow_step_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    workflow_run_id: Mapped[int] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[WorkflowStatus] = mapped_column(
        Enum(
            WorkflowStatus,
            name="workflow_step_status",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column()
    finished_at: Mapped[datetime | None] = mapped_column()
    error_message: Mapped[str | None] = mapped_column(Text)
    workflow_run: Mapped["WorkflowRun"] = relationship(back_populates="steps")
