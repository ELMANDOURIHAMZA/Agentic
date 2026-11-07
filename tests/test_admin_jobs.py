from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import Settings
from app.db import SessionLocal
from app.main import app
from app.models import Job, JobStatus, User, UserRole
from app.security.auth import hash_password


def _user(email: str, role: UserRole) -> None:
    with SessionLocal() as db:
        db.add(
            User(
                first_name="Test",
                last_name="User",
                email=email,
                password_hash=hash_password("StrongPassword!123"),
                role=role,
            )
        )
        db.commit()


def _login(client: TestClient, email: str) -> None:
    csrf = client.get("/login").cookies["csrf_token"]
    response = client.post(
        "/login",
        data={"email": email, "password": "StrongPassword!123", "csrf_token": csrf},
        follow_redirects=False,
    )
    assert response.status_code == 303


def test_admin_only_and_job_transitions() -> None:
    client = TestClient(app)
    assert client.get("/admin/jobs", headers={"accept": "application/json"}).status_code == 401
    candidate_email = f"candidate-{uuid4()}@example.test"
    _user(candidate_email, UserRole.CANDIDATE)
    _login(client, candidate_email)
    assert client.get("/admin/jobs").status_code == 403

    client = TestClient(app)
    admin_email = f"admin-{uuid4()}@example.test"
    _user(admin_email, UserRole.ADMIN)
    _login(client, admin_email)
    page = client.get("/admin/jobs")
    assert page.status_code == 200
    csrf = client.cookies["csrf_token"]

    missing_csrf = client.post(
        "/admin/jobs",
        data={"title": "Python Engineer", "description": "Build APIs"},
    )
    assert missing_csrf.status_code == 403
    csrf = client.cookies["csrf_token"]

    created = client.post(
        "/admin/jobs",
        data={
            "csrf_token": csrf,
            "title": " Python Engineer ",
            "description": "Build APIs and services",
            "required_skills": ["Python", "Python", ""],
            "preferred_skills": ["Docker"],
        },
        follow_redirects=False,
    )
    assert created.status_code == 303
    with SessionLocal() as db:
        job = db.scalar(select(Job).where(Job.title == "Python Engineer"))
        assert job is not None
        job_id = job.id
        assert job.required_skills == ["Python"]

    assert (
        client.post(
            f"/admin/jobs/{job_id}/publish",
            data={"csrf_token": client.cookies["csrf_token"]},
            follow_redirects=False,
        ).status_code
        == 303
    )
    assert (
        client.post(
            f"/admin/jobs/{job_id}/close",
            data={"csrf_token": client.cookies["csrf_token"]},
            follow_redirects=False,
        ).status_code
        == 303
    )
    invalid = client.post(
        f"/admin/jobs/{job_id}/publish",
        data={"csrf_token": client.cookies["csrf_token"]},
        follow_redirects=False,
    )
    assert invalid.status_code == 409
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        assert job is not None
        assert job.status == JobStatus.CLOSED


def test_job_schema_rejects_invalid_fields() -> None:
    client = TestClient(app)
    email = f"schema-admin-{uuid4()}@example.test"
    _user(email, UserRole.ADMIN)
    _login(client, email)
    csrf = client.cookies["csrf_token"]
    response = client.post(
        "/admin/jobs",
        data={
            "csrf_token": csrf,
            "title": "x",
            "description": "short",
            "required_experience_years": -1,
        },
    )
    assert response.status_code == 422


def test_default_secret_is_rejected_outside_development() -> None:
    try:
        Settings(
            DATABASE_URL="postgresql+psycopg://user:pass@localhost/db",
            SECRET_KEY="replace-with-a-local-development-secret",
            APP_ENV="production",
        )
    except ValueError as exc:
        assert "SECRET_KEY" in str(exc)
    else:
        raise AssertionError("The default secret must be rejected outside development")
