"""Separate imported CV benchmark profiles from recruitment entities.

Revision ID: 20261101_0003
Revises: 20261030_0002
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261101_0003"
down_revision: str | None = "20261030_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _hash_file(path: str) -> str:
    try:
        digest = hashlib.sha256()
        with Path(path).open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return hashlib.sha256(path.encode("utf-8")).hexdigest()


def upgrade() -> None:
    bind = op.get_bind()
    imported_status = sa.Enum(
        "NOT_EXTRACTED",
        "EXTRACTED",
        "EXTRACTION_ERROR",
        "QUARANTINED",
        name="imported_profile_status",
    )
    op.create_table(
        "imported_candidate_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_dataset", sa.String(length=255), nullable=False),
        sa.Column("original_filename", sa.String(length=500), nullable=False),
        sa.Column("stored_path", sa.String(length=500), nullable=False),
        sa.Column("extracted_text", sa.Text()),
        sa.Column("professional_category", sa.String(length=200)),
        sa.Column("extraction_status", imported_status, nullable=False),
        sa.Column("imported_at", sa.DateTime(), nullable=False),
        sa.Column("file_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("provenance", sa.JSON(), nullable=False),
    )
    op.create_index(
        "ix_imported_candidate_profiles_source_dataset",
        "imported_candidate_profiles",
        ["source_dataset"],
    )
    op.create_index(
        "ix_imported_candidate_profiles_professional_category",
        "imported_candidate_profiles",
        ["professional_category"],
    )
    op.add_column(
        "jobs",
        sa.Column("is_template", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_jobs_is_template", "jobs", ["is_template"])
    op.alter_column("jobs", "is_template", server_default=None)

    rows = bind.execute(
        sa.text(
            """
            SELECT a.id AS application_id, a.candidate_id, a.job_id,
                   d.stored_path, d.original_name,
                   j.title, u.email
            FROM applications a
            JOIN users u ON u.id = a.candidate_id
            JOIN jobs j ON j.id = a.job_id
            JOIN documents d ON d.application_id = a.id
            WHERE u.email LIKE 'real-dataset-%'
              AND j.title LIKE 'Dataset - %'
              AND d.document_type = 'CV'
            """
        )
    ).mappings()
    for row in rows:
        path = str(row["stored_path"])
        bind.execute(
            sa.text(
                """
                INSERT INTO imported_candidate_profiles
                    (source_dataset, original_filename, stored_path,
                     extracted_text, professional_category, extraction_status,
                     imported_at, file_hash, provenance)
                VALUES
                    (:source, :filename, :path, NULL, :category,
                     'NOT_EXTRACTED', CURRENT_TIMESTAMP, :hash, :provenance)
                ON CONFLICT (file_hash) DO NOTHING
                """
            ),
            {
                "source": "archive (3).zip",
                "filename": str(row["original_name"]),
                "path": path,
                "category": str(row["title"]).removeprefix("Dataset - "),
                "hash": _hash_file(path),
                "provenance": "{}",
            },
        )

    bind.execute(
        sa.text(
            """
            UPDATE jobs
            SET is_template = TRUE, status = 'draft', is_demo = FALSE
            WHERE title LIKE 'Dataset - %'
            """
        )
    )
    bind.execute(
        sa.text(
            """
            DELETE FROM applications
            WHERE candidate_id IN (
                SELECT id FROM users WHERE email LIKE 'real-dataset-%'
            )
            """
        )
    )
    bind.execute(sa.text("DELETE FROM users WHERE email LIKE 'real-dataset-%'"))


def downgrade() -> None:
    bind = op.get_bind()
    count = bind.execute(sa.text("SELECT count(*) FROM imported_candidate_profiles")).scalar_one()
    if count:
        raise RuntimeError(
            "La restauration des données importées doit être faite depuis la sauvegarde "
            "avant de rétrograder cette migration."
        )
    op.drop_index(
        "ix_imported_candidate_profiles_professional_category",
        table_name="imported_candidate_profiles",
    )
    op.drop_index(
        "ix_imported_candidate_profiles_source_dataset",
        table_name="imported_candidate_profiles",
    )
    op.drop_table("imported_candidate_profiles")
    op.drop_index("ix_jobs_is_template", table_name="jobs")
    op.drop_column("jobs", "is_template")
    sa.Enum(name="imported_profile_status").drop(bind, checkfirst=True)
