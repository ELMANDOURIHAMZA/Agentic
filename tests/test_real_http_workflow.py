import io
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import AnalysisResult, Application, ApplicationStatus, Job, User, UserRole
from app.security.auth import hash_password

pytestmark = pytest.mark.integration


def _require_real_provider() -> None:
    if os.getenv("RUN_REAL_LLM_TESTS") != "1":
        pytest.skip("Set RUN_REAL_LLM_TESTS=1 to run billable provider integration tests.")


def _pdf(text: str) -> bytes:
    stream = io.BytesIO()
    document = canvas.Canvas(stream)
    document.drawString(72, 720, text)
    document.save()
    return stream.getvalue()


def _login(client: TestClient, email: str, password: str) -> None:
    csrf_token = client.get("/login").cookies["csrf_token"]
    response = client.post(
        "/login",
        data={"email": email, "password": password, "csrf_token": csrf_token},
        follow_redirects=False,
    )
    assert response.status_code == 303


def test_real_http_recruitment_workflow() -> None:
    _require_real_provider()
    password = "StrongPassword!123"
    admin_email = f"admin-http-{uuid4()}@example.test"
    candidate_email = f"candidate-http-{uuid4()}@example.test"

    with SessionLocal() as db:
        db.add(
            User(
                first_name="Test",
                last_name="Admin",
                email=admin_email,
                password_hash=hash_password(password),
                role=UserRole.ADMIN,
            )
        )
        db.commit()

    admin = TestClient(app)
    candidate = TestClient(app)
    try:
        _login(admin, admin_email, password)

        admin_jobs = admin.get("/admin/jobs")
        assert admin_jobs.status_code == 200
        job_response = admin.post(
            "/admin/jobs",
            data={
                "csrf_token": admin_jobs.cookies["csrf_token"],
                "title": "Python Backend Engineer",
                "description": "Build APIs with Python, FastAPI, and PostgreSQL.",
                "required_skills": ["Python", "FastAPI"],
                "languages": ["English"],
            },
            follow_redirects=False,
        )
        assert job_response.status_code == 303

        with SessionLocal() as db:
            job = db.scalar(select(Job).where(Job.title == "Python Backend Engineer"))
            assert job is not None
            job_id = job.id

        publish = admin.post(
            f"/admin/jobs/{job_id}/publish",
            data={"csrf_token": admin.get("/admin/jobs").cookies["csrf_token"]},
            follow_redirects=False,
        )
        assert publish.status_code == 303

        register_page = candidate.get("/register")
        registered = candidate.post(
            "/register",
            data={
                "first_name": "Alex",
                "last_name": "Martin",
                "email": candidate_email,
                "password": password,
                "csrf_token": register_page.cookies["csrf_token"],
            },
            follow_redirects=False,
        )
        assert registered.status_code == 303
        _login(candidate, candidate_email, password)

        public_jobs = candidate.get("/?q=Python")
        assert public_jobs.status_code == 200
        assert "Python Backend Engineer" in public_jobs.text

        wizard = candidate.get(f"/jobs/{job_id}/apply")
        assert wizard.status_code == 200
        application = candidate.post(
            f"/jobs/{job_id}/apply/confirm",
            data={
                "first_name": "Alex",
                "last_name": "Martin",
                "phone": "+000000000",
                "csrf_token": wizard.cookies["csrf_token"],
            },
            files={
                "cv": (
                    "cv.pdf",
                    _pdf("Alex Martin. Python, FastAPI, PostgreSQL. English."),
                    "application/pdf",
                ),
                "diploma": (
                    "diploma.pdf",
                    _pdf("Fictional diploma for Alex Martin."),
                    "application/pdf",
                ),
                "cin": (
                    "cin.pdf",
                    _pdf("Fictional identity document for Alex Martin."),
                    "application/pdf",
                ),
            },
            follow_redirects=False,
        )
        assert application.status_code == 303

        with SessionLocal() as db:
            stored = db.scalar(
                select(Application)
                .join(User, User.id == Application.candidate_id)
                .where(User.email == candidate_email, Application.job_id == job_id)
            )
            assert stored is not None
            application_id = stored.id
            assert stored.status == ApplicationStatus.PENDING

        admin_applications = admin.get("/admin/applications")
        processed = admin.post(
            "/admin/applications/process",
            data={
                "application_ids": str(application_id),
                "csrf_token": admin_applications.cookies["csrf_token"],
            },
            follow_redirects=False,
        )
        assert processed.status_code == 303

        with SessionLocal() as db:
            stored = db.get(Application, application_id)
            analysis = db.scalar(
                select(AnalysisResult).where(AnalysisResult.application_id == application_id)
            )
            assert stored is not None
            assert stored.status == ApplicationStatus.COMPLETED
            assert analysis is not None
            assert analysis.global_score is not None

        result = candidate.get(f"/candidate/applications/{application_id}/result")
        assert result.status_code == 200
        assert "Dossier conforme." in result.text or "Vérifications incomplètes" in result.text
        assert candidate.get("/admin/jobs").status_code == 403
    finally:
        admin.close()
        candidate.close()
        with SessionLocal() as db:
            db.execute(
                User.__table__.delete().where(User.email.in_([admin_email, candidate_email]))
            )
            db.commit()
