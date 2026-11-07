from uuid import uuid4

from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import Job, JobStatus, User, UserRole
from app.security.auth import hash_password


def _create_user(role: UserRole) -> str:
    email = f"public-{role.value}-{uuid4()}@example.test"
    with SessionLocal() as db:
        db.add(
            User(
                first_name="Public",
                last_name="Test",
                email=email,
                password_hash=hash_password("StrongPassword!123"),
                role=role,
            )
        )
        db.commit()
    return email


def _login(client: TestClient, email: str, next_path: str = "/") -> None:
    csrf = client.get(f"/login?next={next_path}").cookies["csrf_token"]
    response = client.post(
        "/login",
        data={
            "email": email,
            "password": "StrongPassword!123",
            "csrf_token": csrf,
            "next": next_path,
        },
        follow_redirects=False,
    )
    assert response.status_code == 303


def _create_jobs() -> tuple[int, int, int]:
    with SessionLocal() as db:
        jobs = [
            Job(title="Brouillon", description="Non visible", status=JobStatus.DRAFT),
            Job(
                title="Développeur Python",
                description="Construire des APIs",
                required_skills=["Python"],
                location="Tunis",
                status=JobStatus.PUBLISHED,
            ),
            Job(title="Ancienne offre", description="Fermée", status=JobStatus.CLOSED),
        ]
        db.add_all(jobs)
        db.commit()
        return tuple(job.id for job in jobs)


def test_public_visibility_search_pagination_and_detail() -> None:
    client = TestClient(app)
    draft_id, published_id, closed_id = _create_jobs()

    home = client.get("/")
    assert home.status_code == 200
    assert "Développeur Python" in home.text
    assert "Brouillon" not in home.text
    assert "Ancienne offre" not in home.text

    search = client.get("/?q=tUnIs")
    assert "Développeur Python" in search.text
    assert client.get(f"/jobs/{published_id}").status_code == 200
    assert client.get(f"/jobs/{draft_id}").status_code == 404
    assert client.get(f"/jobs/{closed_id}").status_code == 404


def test_public_pagination() -> None:
    with SessionLocal() as db:
        db.add_all(
            [
                Job(
                    title=f"Offre {index}",
                    description="Une description suffisamment longue",
                    status=JobStatus.PUBLISHED,
                )
                for index in range(12)
            ]
        )
        db.commit()
    client = TestClient(app)
    first_page = client.get("/?page=1")
    second_page = client.get("/?page=2")
    assert "Offre 0" in first_page.text
    assert "Offre 11" not in first_page.text
    assert "Offre 11" in second_page.text


def test_application_button_and_role_access() -> None:
    client = TestClient(app)
    _, published_id, _ = _create_jobs()
    detail = client.get(f"/jobs/{published_id}")
    assert f"/login?next=/jobs/{published_id}/apply" in detail.text

    anonymous_apply = client.get(f"/jobs/{published_id}/apply", follow_redirects=False)
    assert anonymous_apply.status_code == 303
    assert f"/login?next=/jobs/{published_id}/apply" in anonymous_apply.headers["location"]

    candidate_email = _create_user(UserRole.CANDIDATE)
    _login(client, candidate_email, f"/jobs/{published_id}/apply")
    assert client.get(f"/jobs/{published_id}/apply").status_code == 200

    admin_client = TestClient(app)
    admin_email = _create_user(UserRole.ADMIN)
    _login(admin_client, admin_email)
    assert admin_client.get(f"/jobs/{published_id}/apply").status_code == 403


def test_html_admin_redirect_json_401_and_open_redirect_rejection() -> None:
    client = TestClient(app)
    admin_page = client.get("/admin/jobs", headers={"accept": "text/html"}, follow_redirects=False)
    assert admin_page.status_code == 303
    assert admin_page.headers["location"] == "/login?next=/admin/jobs"

    api_response = client.get("/candidate", headers={"accept": "application/json"})
    assert api_response.status_code == 401
    assert api_response.json()["detail"] == "Authentication required"

    csrf = client.get("/login?next=https://evil.example").cookies["csrf_token"]
    response = client.post(
        "/login",
        data={
            "email": "missing@example.test",
            "password": "WrongPassword!123",
            "csrf_token": csrf,
            "next": "https://evil.example",
        },
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert "https://evil.example" not in response.text
