import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import psycopg


def test_migrations_upgrade_downgrade_upgrade_on_disposable_schema() -> None:
    database_url = os.environ["DATABASE_URL"]
    psycopg_url = database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    schema = f"migration_test_{uuid4().hex[:12]}"
    with psycopg.connect(psycopg_url, autocommit=True) as connection:
        connection.execute(f'CREATE SCHEMA "{schema}"')
    migration_url = f"{database_url}?options=-csearch_path%3D{schema}".replace("%", "%%")
    environment = os.environ.copy()
    environment["DATABASE_URL"] = migration_url
    root = Path(__file__).resolve().parents[1]
    try:
        commands = (("upgrade", "head"), ("downgrade", "20261030_0001"), ("upgrade", "head"))
        for command, revision in commands:
            result = subprocess.run(
                [sys.executable, "-m", "alembic", command, revision],
                cwd=root,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )
            assert result.returncode == 0, result.stdout + result.stderr
    finally:
        with psycopg.connect(psycopg_url, autocommit=True) as connection:
            connection.execute(f'DROP SCHEMA "{schema}" CASCADE')
