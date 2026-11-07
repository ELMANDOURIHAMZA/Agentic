"""Non-régression des correctifs de robustesse : CSRF, sessions, 422, updated_at, vue candidat."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import Application, Job, JobStatus, User, UserRole
from app.orchestration.workflow import ApplicationWorkflow
from app.seed import seed_demo
from app.services.llm import LLMClient
from tests.llm_fakes import FakeLLM
from tests.test_admin_jobs import _login, _user

PASSWORD = "StrongPassword!123"


def _admin_client() -> tuple[TestClient, str]:
    email = f"admin-{uuid4()}@example.test"
    _user(email, UserRole.ADMIN)
    client = TestClient(app)
    _login(client, email)
    return client, email


def test_csrf_token_is_stable_across_tabs_and_pages() -> None:
    client, _ = _admin_client()
    first = client.get("/admin/jobs")
    token = client.cookies["csrf_token"]
    form_token = first.text.split('name="csrf_token" value="')[1].split('"')[0]
    for url in ("/admin/jobs", "/admin/applications", "/admin/jobs/new"):
        client.get(url)
        assert client.cookies["csrf_token"] == token  # plus de rotation à chaque GET
    # un formulaire ouvert dans le premier onglet reste valide après navigation ailleurs
    created = client.post(
        "/admin/jobs",
        data={
            "title": "Multi-onglets",
            "description": "Description valide.",
            "csrf_token": form_token,
        },
        follow_redirects=False,
    )
    assert created.status_code == 303


def test_csrf_is_still_enforced() -> None:
    client, _ = _admin_client()
    for bad in ("", "x" * 40):
        response = client.post(
            "/admin/jobs",
            data={"title": "t", "description": "d", "csrf_token": bad},
        )
        assert response.status_code == 403


def test_csrf_cookie_is_httponly_and_rotated_on_login() -> None:
    client = TestClient(app)
    before = client.get("/login").cookies["csrf_token"]
    assert "HttpOnly" in client.get("/login").headers["set-cookie"]
    email = f"cand-{uuid4()}@example.test"
    _user(email, UserRole.CANDIDATE)
    _login(client, email)
    assert client.cookies["csrf_token"] != before  # nouvelle session = nouveau jeton


def test_logout_revokes_the_session_server_side() -> None:
    client, _ = _admin_client()
    stolen = client.cookies["auth_token"]
    assert client.get("/admin/jobs").status_code == 200
    out = client.post(
        "/logout", data={"csrf_token": client.cookies["csrf_token"]}, follow_redirects=False
    )
    assert out.status_code == 303
    replay = TestClient(app)
    replay.cookies.set("auth_token", stolen)
    assert replay.get("/admin/jobs", headers={"accept": "application/json"}).status_code == 401


def test_expired_session_token_is_rejected(monkeypatch) -> None:
    from app.security import auth

    client, _ = _admin_client()
    token = client.cookies["auth_token"]
    monkeypatch.setattr(auth, "session_max_age", lambda: -1)
    assert auth.read_auth_token(token) is None


def test_edit_job_with_invalid_data_returns_structured_422() -> None:
    client, _ = _admin_client()
    with SessionLocal() as db:
        job = Job(title="À modifier", description="d", status=JobStatus.DRAFT)
        db.add(job)
        db.commit()
        job_id = job.id
    response = client.post(
        f"/admin/jobs/{job_id}/edit",
        data={
            "title": "",
            "description": "d",
            "required_experience_years": "999",
            "csrf_token": client.cookies["csrf_token"],
        },
        headers={"accept": "application/json"},
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert isinstance(detail, list) and all({"loc", "msg", "type"} <= set(i) for i in detail)


def test_edit_job_updates_updated_at() -> None:
    client, _ = _admin_client()
    old = datetime.now(UTC) - timedelta(days=1)
    with SessionLocal() as db:
        job = Job(title="Horodatage", description="Description initiale", status=JobStatus.DRAFT)
        db.add(job)
        db.commit()
        job.updated_at = old
        db.commit()
        job_id = job.id
    response = client.post(
        f"/admin/jobs/{job_id}/edit",
        data={
            "title": "Horodatage 2",
            "description": "Description modifiée.",
            "csrf_token": client.cookies["csrf_token"],
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    with SessionLocal() as db:
        updated = db.get(Job, job_id).updated_at
    assert updated.replace(tzinfo=UTC) > old + timedelta(hours=1)


def test_candidate_sees_real_compliance_but_never_inconsistency_details(llm_env) -> None:
    with SessionLocal() as db:
        seed_demo(db, PASSWORD)
        rows = {
            email: app_id
            for email, app_id in db.execute(
                select(User.email, Application.id).join(
                    Application, Application.candidate_id == User.id
                )
            )
        }
    for key in ("karim.alaoui", "amina.benali"):
        with SessionLocal() as db:
            ApplicationWorkflow(LLMClient(transport=FakeLLM())).run(db, rows[f"{key}@example.test"])
    clean = TestClient(app)
    _login_as(clean, "amina.benali@example.test")
    flagged = TestClient(app)
    _login_as(flagged, "karim.alaoui@example.test")

    page = clean.get(f"/candidate/applications/{rows['amina.benali@example.test']}/result")
    assert page.status_code == 200 and "Dossier conforme." in page.text
    assert "100" in page.text and "Python" in page.text

    karim_url = f"/candidate/applications/{rows['karim.alaoui@example.test']}/result"
    page = flagged.get(karim_url)
    assert page.status_code == 200 and "Dossier conforme." not in page.text
    for secret in ("Chraibi", "incohérence", "titulaire", "ZZ000005", "rapport"):
        assert secret.casefold() not in page.text.casefold()
    # accès croisé refusé côté serveur
    assert clean.get(karim_url).status_code in {403, 404}
    assert flagged.get(
        f"/candidate/applications/{rows['amina.benali@example.test']}/result"
    ).status_code in {403, 404}
    # le rapport complet reste réservé à l'admin
    admin, _ = _admin_client()
    report = admin.get(f"/admin/applications/{rows['karim.alaoui@example.test']}")
    assert report.status_code == 200 and "Chraibi" in report.text


def _login_as(client: TestClient, email: str) -> None:
    csrf = client.get("/login").cookies["csrf_token"]
    response = client.post(
        "/login",
        data={"email": email, "password": PASSWORD, "csrf_token": csrf},
        follow_redirects=False,
    )
    assert response.status_code == 303
