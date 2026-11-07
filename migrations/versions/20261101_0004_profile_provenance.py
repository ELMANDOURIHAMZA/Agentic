"""Backfill provenance for profiles imported by the previous migration."""

from __future__ import annotations

import json
from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261101_0004"
down_revision: str | None = "20261101_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            """
            SELECT id, source_dataset, original_filename, stored_path, provenance
            FROM imported_candidate_profiles
            WHERE provenance::text = :empty
            """
        ),
        {"empty": "{}"},
    ).mappings()
    for row in rows:
        bind.execute(
            sa.text(
                """
                UPDATE imported_candidate_profiles
                SET provenance = CAST(:provenance AS json)
                WHERE id = :id
                """
            ),
            {
                "id": row["id"],
                "provenance": json.dumps(
                    {
                        "archive_member": row["original_filename"],
                        "source_dataset": row["source_dataset"],
                        "stored_path": row["stored_path"],
                        "migration": "20261101_0004",
                    }
                ),
            },
        )


def downgrade() -> None:
    bind = op.get_bind()
    count = bind.execute(
        sa.text(
            """
            SELECT count(*)
            FROM imported_candidate_profiles
            WHERE provenance->>'migration' = '20261101_0004'
            """
        )
    ).scalar_one()
    if count:
        raise RuntimeError(
            "La provenance des profils importés ne peut pas être restaurée sans "
            "supprimer des métadonnées potentiellement modifiées."
        )
