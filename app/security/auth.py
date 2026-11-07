import re
import secrets
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import get_settings

password_hasher = PasswordHasher()
_attempts: defaultdict[str, list[datetime]] = defaultdict(list)
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PASSWORD_PATTERN = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z\d]).{12,}$")
MAX_LOGIN_ATTEMPTS = 5
LOGIN_WINDOW = timedelta(minutes=15)


def validate_email(email: str) -> bool:
    return bool(_EMAIL_PATTERN.fullmatch(email))


def validate_password_strength(password: str) -> bool:
    return bool(_PASSWORD_PATTERN.fullmatch(password))


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (InvalidHashError, VerificationError, VerifyMismatchError):
        return False


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().secret_key, salt="recruitment-auth")


def create_auth_token(user_id: int, csrf_token: str) -> str:
    return _serializer().dumps({"user_id": user_id, "csrf": csrf_token})


def read_auth_token(token: str) -> dict[str, Any] | None:
    try:
        payload = _serializer().loads(token, max_age=int(timedelta(days=30).total_seconds()))
    except (BadSignature, SignatureExpired):
        return None
    return payload if isinstance(payload, dict) and "user_id" in payload else None


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def is_login_allowed(client_key: str) -> bool:
    now = datetime.now(UTC)
    recent = [attempt for attempt in _attempts[client_key] if now - attempt < LOGIN_WINDOW]
    _attempts[client_key] = recent
    return len(recent) < MAX_LOGIN_ATTEMPTS


def record_login_attempt(client_key: str) -> None:
    _attempts[client_key].append(datetime.now(UTC))
