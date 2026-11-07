from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.config import get_settings
from app.db import SessionLocal
from app.main import app
from app.models import User, UserRole
from app.security.auth import hash_password


def _email() -> str:
    return f"auth-{uuid4()}@example.test"


def test_registration_login_csrf_roles_and_logout() -> None:
    client = TestClient(app)
    email = _email()
    password = "StrongPassword!123"

    unauthenticated = client.get("/candidate", headers={"accept": "application/json"})
    assert unauthenticated.status_code == 401

    register_page = client.get("/register")
    assert register_page.status_code == 200
    csrf_token = client.cookies.get("csrf_token")
    assert csrf_token

    missing_csrf = client.post(
        "/register",
        data={
            "first_name": "Ada",
            "last_name": "Candidate",
            "email": email,
            "password": password,
        },
    )
    assert missing_csrf.status_code == 403

    registered = client.post(
        "/register",
        data={
            "first_name": "Ada",
            "last_name": "Candidate",
            "email": email,
            "password": password,
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )
    assert registered.status_code == 303

    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).one()
        assert user.password_hash != password

    client.get("/login")
    login_csrf = client.cookies.get("csrf_token")
    assert login_csrf
    invalid = client.post(
        "/login",
        data={"email": email, "password": "WrongPassword!123", "csrf_token": login_csrf},
    )
    assert invalid.status_code == 200
    assert "Identifiants invalides." in invalid.text

    valid = client.post(
        "/login",
        data={"email": email, "password": password, "csrf_token": login_csrf},
        follow_redirects=False,
    )
    assert valid.status_code == 303
    assert client.get("/candidate").status_code == 200
    assert client.get("/admin/jobs").status_code == 403

    logged_out = client.post(
        "/logout",
        data={"csrf_token": client.cookies.get("csrf_token")},
        follow_redirects=False,
    )
    assert logged_out.status_code == 303
    assert client.get("/candidate", headers={"accept": "application/json"}).status_code == 401

    with SessionLocal() as db:
        db.execute(delete(User).where(User.email == email))
        db.commit()


def test_admin_route_accepts_admin_and_password_is_hashed() -> None:
    client = TestClient(app)
    email = _email()
    password = "AdminPassword!123"
    with SessionLocal() as db:
        db.add(
            User(
                first_name="Admin",
                last_name="Test",
                email=email,
                password_hash=hash_password(password),
                role=UserRole.ADMIN,
            )
        )
        db.commit()
    try:
        csrf = client.get("/login").cookies["csrf_token"]
        response = client.post(
            "/login",
            data={"email": email, "password": password, "csrf_token": csrf},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert client.get("/admin/jobs").status_code == 200
    finally:
        with SessionLocal() as db:
            db.execute(delete(User).where(User.email == email))
            db.commit()


def test_candidate_page_escapes_html_in_user_name() -> None:
    email = f"xss-{uuid4()}@example.test"
    with SessionLocal() as db:
        db.add(
            User(
                first_name="<script>alert(1)</script>",
                last_name="Test",
                email=email,
                password_hash=hash_password("StrongPassword!123"),
                role=UserRole.CANDIDATE,
            )
        )
        db.commit()
    try:
        client = TestClient(app)
        csrf = client.get("/login").cookies["csrf_token"]
        response = client.post(
            "/login",
            data={"email": email, "password": "StrongPassword!123", "csrf_token": csrf},
            follow_redirects=False,
        )
        assert response.status_code == 303
        page = client.get("/candidate")
        assert "<script>alert(1)</script>" not in page.text
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page.text
    finally:
        with SessionLocal() as db:
            db.execute(delete(User).where(User.email == email))
            db.commit()


def test_auth_cookie_is_secure_outside_development(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "test-production-secret")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test-production-password")
    get_settings.cache_clear()
    email = _email()
    password = "AdminPassword!123"
    with SessionLocal() as db:
        db.add(
            User(
                first_name="Admin",
                last_name="Secure",
                email=email,
                password_hash=hash_password(password),
                role=UserRole.ADMIN,
            )
        )
        db.commit()
    try:
        client = TestClient(app)
        csrf = client.get("/login").cookies["csrf_token"]
        response = client.post(
            "/login",
            data={"email": email, "password": password, "csrf_token": csrf},
            follow_redirects=False,
        )
        assert "auth_token=" in response.headers["set-cookie"]
        assert "Secure" in response.headers["set-cookie"]
    finally:
        with SessionLocal() as db:
            db.execute(delete(User).where(User.email == email))
            db.commit()
        monkeypatch.setenv("APP_ENV", "development")
        get_settings.cache_clear()


def _login_candidate(client: TestClient) -> str:
    email = _email()
    password = "StrongPassword!123"
    with SessionLocal() as db:
        db.add(
            User(
                first_name="Logout",
                last_name="Test",
                email=email,
                password_hash=hash_password(password),
                role=UserRole.CANDIDATE,
            )
        )
        db.commit()
    csrf = client.get("/login").cookies["csrf_token"]
    response = client.post(
        "/login",
        data={"email": email, "password": password, "csrf_token": csrf},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return email


def _cleanup(email: str) -> None:
    with SessionLocal() as db:
        db.execute(delete(User).where(User.email == email))
        db.commit()


def test_logout_button_rendered_in_each_space_works_after_csrf_rotation() -> None:
    import re

    client = TestClient(app)
    email = _login_candidate(client)
    try:
        for path in ("/candidate", "/candidate/applications", "/candidate/profile", "/"):
            page = client.get(path)  # chaque page candidat renouvelle le cookie CSRF
            assert 'action="/logout"' in page.text, path
        page = client.get("/candidate/applications")
        token = re.search(r'action="/logout".*?value="([^"]+)"', page.text, re.S).group(1)
        assert token == client.cookies.get("csrf_token")
        done = client.post("/logout", data={"csrf_token": token}, follow_redirects=False)
        assert done.status_code == 303
        assert client.get("/candidate", headers={"accept": "application/json"}).status_code == 401
    finally:
        _cleanup(email)


def test_logout_with_wrong_csrf_is_refused_and_session_kept() -> None:
    client = TestClient(app)
    email = _login_candidate(client)
    try:
        refused = client.post("/logout", data={"csrf_token": "forged"}, follow_redirects=False)
        assert refused.status_code == 403
        assert client.get("/candidate").status_code == 200
    finally:
        _cleanup(email)


def test_logout_button_hidden_for_anonymous_visitors() -> None:
    assert 'action="/logout"' not in TestClient(app).get("/").text
