"""Add explicit certification requirements to jobs."""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261105_0005"
down_revision: str | None = "20261101_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column("required_certifications", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.alter_column("jobs", "required_certifications", server_default=None)


def downgrade() -> None:
    op.drop_column("jobs", "required_certifications")
