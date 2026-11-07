from uuid import uuid4

from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.models import User, UserRole
from app.security.auth import hash_password


def _admin() -> str:
    email = f"admin-{uuid4()}@example.test"
    with SessionLocal() as db:
        db.add(
            User(
                first_name="Test",
                last_name="Admin",
                email=email,
                password_hash=hash_password("StrongPassword!123"),
                role=UserRole.ADMIN,
            )
        )
        db.commit()
    return email


def _login(client: TestClient, email: str) -> None:
    csrf_token = client.get("/login").cookies["csrf_token"]
    response = client.post(
        "/login",
        data={"email": email, "password": "StrongPassword!123", "csrf_token": csrf_token},
        follow_redirects=False,
    )
    assert response.status_code == 303
