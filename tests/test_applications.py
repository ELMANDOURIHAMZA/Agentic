from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.config import get_settings
from app.db import SessionLocal
from app.main import app
from app.models import (
    Application,
    ApplicationStatus,
    Document,
    Job,
    JobStatus,
    User,
    UserRole,
    WorkflowRun,
)
from app.security.auth import hash_password


def _create_user(role: UserRole) -> str:
    email = f"application-{role.value}-{uuid4()}@example.test"
    with SessionLocal() as db:
        db.add(
            User(
                first_name="Candidate",
                last_name="Test",
                email=email,
                password_hash=hash_password("StrongPassword!123"),
                role=role,
            )
        )
        db.commit()
    return email


def _create_published_job() -> int:
    with SessionLocal() as db:
        job = Job(title="Secure job", description="A published job", status=JobStatus.PUBLISHED)
        db.add(job)
        db.commit()
        return job.id


def _login(client: TestClient, email: str) -> None:
    csrf = client.get("/login").cookies["csrf_token"]
    response = client.post(
        "/login",
        data={"email": email, "password": "StrongPassword!123", "csrf_token": csrf},
        follow_redirects=False,
    )
    assert response.status_code == 303


def _files(**overrides: tuple[str, bytes, str]) -> dict[str, tuple[str, BytesIO, str]]:
    defaults = {
        "cv": ("cv.pdf", b"%PDF-1.7\ncv", "application/pdf"),
        "diploma": ("diploma.pdf", b"%PDF-1.7\ndiploma", "application/pdf"),
        "cin": ("cin.png", b"\x89PNG\r\n\x1a\ncin", "image/png"),
    }
    defaults.update(overrides)
    return {key: (name, BytesIO(content), mime) for key, (name, content, mime) in defaults.items()}


def _confirm(client: TestClient, job_id: int, files: dict) -> object:
    return client.post(
        f"/jobs/{job_id}/apply/confirm",
        data={
            "csrf_token": client.cookies["csrf_token"],
            "first_name": "Updated",
            "last_name": "Candidate",
            "phone": "+21600000000",
        },
        files=files,
        follow_redirects=False,
    )


def test_complete_application_is_pending_without_workflow() -> None:
    email = _create_user(UserRole.CANDIDATE)
    job_id = _create_published_job()
    client = TestClient(app)
    _login(client, email)
    response = _confirm(client, job_id, _files())
    assert response.status_code == 303
    with SessionLocal() as db:
        application = db.scalar(select(Application))
        assert application is not None
        assert application.status == ApplicationStatus.PENDING
        assert db.scalar(select(func.count()).select_from(WorkflowRun)) == 0
        assert db.scalar(select(func.count()).select_from(Document)) == 3


def test_missing_bad_and_large_files_are_rejected_and_cleaned() -> None:
    email = _create_user(UserRole.CANDIDATE)
    job_id = _create_published_job()
    client = TestClient(app)
    _login(client, email)
    missing = client.post(
        f"/jobs/{job_id}/apply/confirm",
        data={"csrf_token": client.cookies["csrf_token"], "first_name": "A", "last_name": "B"},
        files={"cv": _files()["cv"]},
    )
    assert missing.status_code == 422
    bad_files = _files()
    bad_files["diploma"] = ("diploma.pdf", BytesIO(b"not a pdf"), "application/pdf")
    response = _confirm(client, job_id, bad_files)
    assert response.status_code == 400
    from tests.conftest import UPLOAD_ROOT

    assert list(UPLOAD_ROOT.iterdir()) == []
    oversized = _files(
        cv=(
            "cv.pdf",
            b"%PDF-" + b"x" * (get_settings().max_upload_mb * 1024 * 1024 + 1),
            "application/pdf",
        )
    )
    assert _confirm(client, job_id, oversized).status_code == 413


def test_duplicate_application_and_non_published_job_are_rejected() -> None:
    email = _create_user(UserRole.CANDIDATE)
    job_id = _create_published_job()
    client = TestClient(app)
    _login(client, email)
    assert _confirm(client, job_id, _files()).status_code == 303
    duplicate = _confirm(client, job_id, _files())
    assert duplicate.status_code == 200
    assert "déjà candidaté" in duplicate.text
    with SessionLocal() as db:
        closed = Job(title="Closed", description="Closed", status=JobStatus.CLOSED)
        db.add(closed)
        db.commit()
        closed_id = closed.id
    assert client.get(f"/jobs/{closed_id}/apply").status_code == 404


def test_document_access_owner_admin_other_candidate_and_anonymous() -> None:
    owner_email = _create_user(UserRole.CANDIDATE)
    job_id = _create_published_job()
    owner = TestClient(app)
    _login(owner, owner_email)
    assert _confirm(owner, job_id, _files()).status_code == 303
    with SessionLocal() as db:
        document_id = db.scalar(select(Document.id))
    assert document_id is not None
    downloaded = owner.get(f"/documents/{document_id}")
    assert downloaded.status_code == 200
    assert downloaded.headers["x-content-type-options"] == "nosniff"
    assert "attachment" in downloaded.headers["content-disposition"]
    other = TestClient(app)
    _login(other, _create_user(UserRole.CANDIDATE))
    assert other.get(f"/documents/{document_id}").status_code == 403
    admin = TestClient(app)
    _login(admin, _create_user(UserRole.ADMIN))
    assert admin.get(f"/documents/{document_id}").status_code == 200
    assert (
        TestClient(app)
        .get(f"/documents/{document_id}", headers={"accept": "application/json"})
        .status_code
        == 401
    )


def test_document_download_rejects_path_outside_upload_directory() -> None:
    email = _create_user(UserRole.CANDIDATE)
    job_id = _create_published_job()
    client = TestClient(app)
    _login(client, email)
    assert _confirm(client, job_id, _files()).status_code == 303
    with SessionLocal() as db:
        document = db.scalar(select(Document))
        assert document is not None
        document.stored_path = str(Path.cwd().parent / "outside.pdf")
        document_id = document.id
        db.commit()
    assert client.get(f"/documents/{document_id}").status_code == 404


def test_application_csrf_and_mime_validation() -> None:
    email = _create_user(UserRole.CANDIDATE)
    job_id = _create_published_job()
    client = TestClient(app)
    _login(client, email)
    csrf_rejected = client.post(
        f"/jobs/{job_id}/apply/confirm",
        data={"first_name": "A", "last_name": "B", "phone": ""},
        files=_files(),
    )
    assert csrf_rejected.status_code == 200
    invalid_mime = _files()
    invalid_mime["cv"] = ("cv.pdf", BytesIO(b"%PDF-1.7"), "image/png")
    response = _confirm(client, job_id, invalid_mime)
    assert response.status_code == 400
