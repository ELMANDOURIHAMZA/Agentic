import os
import shutil
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from tempfile import mkdtemp

import psycopg
import pytest
from sqlalchemy import delete

ROOT = Path(__file__).resolve().parents[1]
UPLOAD_ROOT = Path(mkdtemp(prefix="recruitment-test-uploads-"))
os.environ["UPLOAD_DIR"] = str(UPLOAD_ROOT)
os.environ["SMTP_HOST"] = ""
TEST_DATABASE_URL = (
    "postgresql+psycopg://recruitment_user:change-me@localhost:5432/recruitment_test"
)


def _ensure_test_database() -> None:
    with psycopg.connect(
        "postgresql://recruitment_user:change-me@localhost:5432/postgres",
        autocommit=True,
    ) as connection:
        exists = connection.execute(
            "SELECT 1 FROM pg_database WHERE datname = 'recruitment_test'"
        ).fetchone()
        if exists is None:
            connection.execute("CREATE DATABASE recruitment_test")


_ensure_test_database()
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
subprocess.run(
    [sys.executable, "-m", "alembic", "upgrade", "head"],
    cwd=ROOT,
    env=os.environ.copy(),
    check=True,
    capture_output=True,
    text=True,
)

from app.db import SessionLocal  # noqa: E402
from app.models import Base  # noqa: E402


@pytest.fixture(autouse=True)
def clean_test_database() -> Iterator[None]:
    yield
    with SessionLocal() as db:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(delete(table))
        db.commit()
    for path in UPLOAD_ROOT.iterdir():
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
