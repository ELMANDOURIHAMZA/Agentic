from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import (
    AnalysisResult,
    Application,
    ApplicationStatus,
    Job,
    User,
    UserRole,
)
from app.security.auth import hash_password

STATUS_LABELS = {
    ApplicationStatus.SUBMITTED: "Candidature envoyée",
    ApplicationStatus.PENDING: "En attente de traitement",
    ApplicationStatus.PROCESSING: "En cours de traitement",
    ApplicationStatus.COMPLETED: "Analyse terminée",
    ApplicationStatus.ERROR: "Erreur de traitement",
}


def _user(role: UserRole) -> str:
    email = f"candidate-space-{uuid4()}@example.test"
    with SessionLocal() as db:
        db.add(
            User(
                first_name="Test",
                last_name="Candidate",
                email=email,
                password_hash=hash_password("StrongPassword!123"),
                role=role,
            )
        )
        db.commit()
    return email


def _login(client: TestClient, email: str) -> None:
    csrf = client.get("/login").cookies["csrf_token"]
    response = client.post(
        "/login",
        data={"email": email, "password": "StrongPassword!123", "csrf_token": csrf},
        follow_redirects=False,
    )
    assert response.status_code == 303


def _application(email: str, status: ApplicationStatus) -> int:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        job = Job(title=f"Job {uuid4()}", description="Description")
        db.add(job)
        db.flush()
        application = Application(candidate_id=user.id, job_id=job.id, status=status)
        db.add(application)
        db.commit()
        return application.id


def test_candidate_isolation_and_access_roles() -> None:
    first_email = _user(UserRole.CANDIDATE)
    second_email = _user(UserRole.CANDIDATE)
    application_id = _application(first_email, ApplicationStatus.PENDING)
    first = TestClient(app)
    _login(first, first_email)
    assert first.get("/candidate").status_code == 200
    assert first.get(f"/candidate/applications/{application_id}").status_code == 200
    second = TestClient(app)
    _login(second, second_email)
    assert second.get(f"/candidate/applications/{application_id}").status_code == 404
    admin = TestClient(app)
    _login(admin, _user(UserRole.ADMIN))
    assert admin.get("/candidate").status_code == 403
    assert TestClient(app).get("/candidate", follow_redirects=False).status_code == 303


def test_profile_update_validation_and_csrf() -> None:
    email = _user(UserRole.CANDIDATE)
    client = TestClient(app)
    _login(client, email)
    profile = client.get("/candidate/profile")
    csrf = profile.cookies["csrf_token"]
    invalid = client.post(
        "/candidate/profile",
        data={"first_name": "", "last_name": "Valid", "csrf_token": csrf},
    )
    assert invalid.status_code == 200
    assert "Profil invalide." in invalid.text
    missing_csrf = client.post(
        "/candidate/profile", data={"first_name": "New", "last_name": "Name"}
    )
    assert missing_csrf.status_code == 403
    updated = client.post(
        "/candidate/profile",
        data={
            "first_name": " New ",
            "last_name": " Name ",
            "phone": "+216000000",
            "csrf_token": client.cookies["csrf_token"],
        },
        follow_redirects=False,
    )
    assert updated.status_code == 303
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        assert user.first_name == "New"
        assert user.last_name == "Name"


def test_french_status_labels_and_error_hidden() -> None:
    email = _user(UserRole.CANDIDATE)
    ids = [_application(email, value) for value in STATUS_LABELS]
    client = TestClient(app)
    _login(client, email)
    page = client.get("/candidate/applications")
    for label in STATUS_LABELS.values():
        assert label in page.text
    with SessionLocal() as db:
        application = db.get(Application, ids[-1])
        application.error_message = "SECRET TECHNIQUE"
        db.commit()
    detail = client.get(f"/candidate/applications/{ids[-1]}")
    assert "SECRET TECHNIQUE" not in detail.text


def test_candidate_result_view_is_restricted_and_sanitized() -> None:
    email = _user(UserRole.CANDIDATE)
    application_id = _application(email, ApplicationStatus.PENDING)
    client = TestClient(app)
    _login(client, email)
    pending = client.get(f"/candidate/applications/{application_id}/result")
    assert "résultats seront disponibles" in pending.text
    with SessionLocal() as db:
        application = db.get(Application, application_id)
        application.status = ApplicationStatus.COMPLETED
        db.add(
            AnalysisResult(
                application_id=application_id,
                global_score=87.5,
                matching_skills=["Python"],
                missing_skills=["Docker"],
                score_details={"private": "INTERNAL", "inconsistencies": ["INCOHERENCE PRIVEE"]},
                report="RAPPORT DÉTAILLÉ SECRET INCOHERENCE PRIVEE",
            )
        )
        db.commit()
    result = client.get(f"/candidate/applications/{application_id}/result")
    assert "87.5" in result.text
    assert "Python" in result.text
    assert "Docker" in result.text
    assert "RAPPORT DÉTAILLÉ SECRET" not in result.text
    assert "INTERNAL" not in result.text
    assert "INCOHERENCE PRIVEE" not in result.text
