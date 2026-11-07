"""Create initial recruitment data model.

Revision ID: 20261030_0001
Revises:
Create Date: 2026-10-30
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261030_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    user_role = sa.Enum("admin", "candidate", name="user_role")
    job_status = sa.Enum("draft", "published", "closed", name="job_status")
    application_status = sa.Enum(
        "SUBMITTED",
        "PENDING",
        "PROCESSING",
        "COMPLETED",
        "ERROR",
        name="application_status",
    )
    document_type = sa.Enum("CV", "DIPLOMA", "CIN", name="document_type")
    workflow_status = sa.Enum("PENDING", "RUNNING", "COMPLETED", "ERROR", name="workflow_status")
    workflow_step_status = sa.Enum(
        "PENDING",
        "RUNNING",
        "COMPLETED",
        "ERROR",
        name="workflow_step_status",
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("phone", sa.String(length=30)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("required_degree", sa.String(length=200)),
        sa.Column("required_experience_years", sa.Integer(), nullable=False),
        sa.Column("required_skills", sa.JSON(), nullable=False),
        sa.Column("preferred_skills", sa.JSON(), nullable=False),
        sa.Column("languages", sa.JSON(), nullable=False),
        sa.Column("other_requirements", sa.Text()),
        sa.Column("location", sa.String(length=200)),
        sa.Column("status", job_status, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("published_at", sa.DateTime()),
        sa.Column("closed_at", sa.DateTime()),
    )
    op.create_index("ix_jobs_title", "jobs", ["title"])
    op.create_index("ix_jobs_status", "jobs", ["status"])
    op.create_table(
        "applications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "candidate_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "job_id", sa.Integer(), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("applied_at", sa.DateTime(), nullable=False),
        sa.Column("status", application_status, nullable=False),
        sa.Column("error_message", sa.Text()),
        sa.UniqueConstraint("candidate_id", "job_id", name="uq_applications_candidate_job"),
    )
    op.create_index("ix_applications_candidate_id", "applications", ["candidate_id"])
    op.create_index("ix_applications_job_id", "applications", ["job_id"])
    op.create_index("ix_applications_status", "applications", ["status"])
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "application_id",
            sa.Integer(),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("document_type", document_type, nullable=False),
        sa.Column("stored_path", sa.String(length=500), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("imported_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_documents_application_id", "documents", ["application_id"])
    for table, json_name in (
        ("structured_requirements", "job_id"),
        ("extracted_profiles", "application_id"),
        ("document_verifications", "application_id"),
    ):
        foreign_table = "jobs" if table == "structured_requirements" else "applications"
        op.create_table(
            table,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                json_name,
                sa.Integer(),
                sa.ForeignKey(f"{foreign_table}.id", ondelete="CASCADE"),
                nullable=False,
                unique=True,
            ),
            sa.Column("data", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
    op.create_table(
        "analysis_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "application_id",
            sa.Integer(),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("global_score", sa.Float(), nullable=False),
        sa.Column("score_details", sa.JSON(), nullable=False),
        sa.Column("matching_skills", sa.JSON(), nullable=False),
        sa.Column("missing_skills", sa.JSON(), nullable=False),
        sa.Column("report", sa.Text(), nullable=False),
        sa.Column("analyzed_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "workflow_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "application_id",
            sa.Integer(),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", workflow_status, nullable=False),
        sa.Column("started_at", sa.DateTime()),
        sa.Column("finished_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_workflow_runs_application_id", "workflow_runs", ["application_id"])
    op.create_table(
        "workflow_step_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "workflow_run_id",
            sa.Integer(),
            sa.ForeignKey("workflow_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("agent", sa.String(length=100), nullable=False),
        sa.Column("status", workflow_step_status, nullable=False),
        sa.Column("started_at", sa.DateTime()),
        sa.Column("finished_at", sa.DateTime()),
        sa.Column("error_message", sa.Text()),
    )
    op.create_index(
        "ix_workflow_step_logs_workflow_run_id", "workflow_step_logs", ["workflow_run_id"]
    )
    op.create_index("ix_workflow_step_logs_agent", "workflow_step_logs", ["agent"])


def downgrade() -> None:
    for table in (
        "workflow_step_logs",
        "workflow_runs",
        "analysis_results",
        "document_verifications",
        "extracted_profiles",
        "structured_requirements",
        "documents",
        "applications",
        "jobs",
        "users",
    ):
        op.drop_table(table)
    for enum_name in (
        "workflow_step_status",
        "workflow_status",
        "document_type",
        "application_status",
        "job_status",
        "user_role",
    ):
        sa.Enum(name=enum_name).drop(op.get_bind(), checkfirst=True)
