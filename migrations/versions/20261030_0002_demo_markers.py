"""Add explicit markers for demonstration data.

Revision ID: 20261030_0002
Revises: 20261030_0001
Create Date: 2026-10-30
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261030_0002"
down_revision: Union[str, None] = "20261030_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "jobs",
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_users_is_demo", "users", ["is_demo"])
    op.create_index("ix_jobs_is_demo", "jobs", ["is_demo"])
    op.alter_column("users", "is_demo", server_default=None)
    op.alter_column("jobs", "is_demo", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_jobs_is_demo", table_name="jobs")
    op.drop_index("ix_users_is_demo", table_name="users")
    op.drop_column("jobs", "is_demo")
    op.drop_column("users", "is_demo")
