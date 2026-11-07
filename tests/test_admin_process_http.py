"""Déclenchement manuel via HTTP : /process et /retry (LLM simulé injecté dans la route)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api import admin_applications
from app.db import SessionLocal
from app.main import app
from app.models import AnalysisResult, Application, ApplicationStatus, User, UserRole
from app.seed import DEMO_ADMIN_EMAIL, seed_demo
from app.services.llm import LLMClient
from tests.llm_fakes import FakeLLM

PASSWORD = "StrongPassword!123"


def _client(email: str) -> TestClient:
    client = TestClient(app)
    csrf = client.get("/login").cookies["csrf_token"]
    response = client.post(
        "/login",
        data={"email": email, "password": PASSWORD, "csrf_token": csrf},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return client


@pytest.fixture
def seeded(llm_env, monkeypatch) -> dict[str, int]:
    fake = FakeLLM()
    monkeypatch.setattr(admin_applications, "build_llm_client", lambda: LLMClient(transport=fake))
    with SessionLocal() as db:
        seed_demo(db, PASSWORD)
        return {
            email.removesuffix("@example.test"): app_id
            for email, app_id in db.execute(
                select(User.email, Application.id).join(
                    Application, Application.candidate_id == User.id
                )
            )
        }


def _status(app_id: int) -> ApplicationStatus:
    with SessionLocal() as db:
        return db.get(Application, app_id).status


def test_seeded_applications_stay_pending_until_admin_acts(seeded) -> None:
    assert {_status(i) for i in seeded.values()} == {ApplicationStatus.PENDING}
    with SessionLocal() as db:
        assert db.scalar(select(AnalysisResult)) is None  # aucune analyse automatique


def test_admin_selects_several_applications_and_triggers_processing(seeded) -> None:
    admin = _client(DEMO_ADMIN_EMAIL)
    page = admin.get("/admin/applications")
    assert page.status_code == 200
    chosen = [seeded["amina.benali"], seeded["karim.alaoui"]]
    response = admin.post(
        "/admin/applications/process",
        data={
            "application_ids": [str(i) for i in chosen],
            "csrf_token": admin.cookies["csrf_token"],
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert [_status(i) for i in chosen] == [ApplicationStatus.COMPLETED] * 2
    # les candidatures non sélectionnées ne sont pas touchées
    assert _status(seeded["youssef.tazi"]) == ApplicationStatus.PENDING
    detail = admin.get(f"/admin/applications/{seeded['karim.alaoui']}")
    assert "Chraibi" in detail.text and "Revue humaine obligatoire" in detail.text


def test_process_requires_admin_role_and_csrf(seeded) -> None:
    target = seeded["amina.benali"]
    candidate = _client("amina.benali@example.test")
    denied = candidate.post(
        "/admin/applications/process",
        data={"application_ids": str(target), "csrf_token": candidate.cookies["csrf_token"]},
        follow_redirects=False,
    )
    assert denied.status_code == 403
    anonymous = TestClient(app).post(
        "/admin/applications/process", data={"application_ids": str(target)}, follow_redirects=False
    )
    assert anonymous.status_code in {401, 303}
    admin = _client(DEMO_ADMIN_EMAIL)
    no_csrf = admin.post(
        "/admin/applications/process",
        data={"application_ids": str(target), "csrf_token": "faux"},
        follow_redirects=False,
    )
    assert no_csrf.status_code == 403
    assert _status(target) == ApplicationStatus.PENDING


def test_failed_run_then_retry_from_admin_ui(seeded, monkeypatch) -> None:
    target = seeded["youssef.tazi"]
    admin = _client(DEMO_ADMIN_EMAIL)
    broken = FakeLLM({"SemanticEvaluationOut": RuntimeError("panne")})
    monkeypatch.setattr(admin_applications, "build_llm_client", lambda: LLMClient(transport=broken))
    admin.post(
        "/admin/applications/process",
        data={"application_ids": str(target), "csrf_token": admin.cookies["csrf_token"]},
        follow_redirects=False,
    )
    assert _status(target) == ApplicationStatus.ERROR
    monkeypatch.setattr(
        admin_applications, "build_llm_client", lambda: LLMClient(transport=FakeLLM())
    )
    retry = admin.post(
        f"/admin/applications/{target}/retry",
        data={"csrf_token": admin.cookies["csrf_token"]},
        follow_redirects=False,
    )
    assert retry.status_code == 303 and _status(target) == ApplicationStatus.COMPLETED


def test_completed_application_cannot_be_reprocessed(seeded) -> None:
    target = seeded["omar.fassi"]
    admin = _client(DEMO_ADMIN_EMAIL)
    for _ in range(2):
        admin.post(
            "/admin/applications/process",
            data={"application_ids": str(target), "csrf_token": admin.cookies["csrf_token"]},
            follow_redirects=False,
        )
    with SessionLocal() as db:
        results = list(
            db.scalars(select(AnalysisResult).where(AnalysisResult.application_id == target))
        )
    assert len(results) == 1 and _status(target) == ApplicationStatus.COMPLETED


def test_misconfigured_llm_leaves_applications_pending(seeded, monkeypatch) -> None:
    from fastapi import HTTPException

    def refuse() -> LLMClient:
        raise HTTPException(status_code=503, detail="Clé LLM absente.")

    monkeypatch.setattr(admin_applications, "build_llm_client", refuse)
    target = seeded["salma.idrissi"]
    admin = _client(DEMO_ADMIN_EMAIL)
    response = admin.post(
        "/admin/applications/process",
        data={"application_ids": str(target), "csrf_token": admin.cookies["csrf_token"]},
        follow_redirects=False,
    )
    assert response.status_code == 503
    assert _status(target) == ApplicationStatus.PENDING  # pas de statut bloqué en PROCESSING
