import asyncio
from email.message import EmailMessage
from pathlib import Path

import pytest

from app.config import get_settings
from app.services import email_service


def test_two_notifications_use_safe_headers_and_no_sensitive_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    settings.smtp_host = "fake.smtp.test"
    settings.smtp_starttls = True
    settings.admin_notification_email = "admin@example.test"
    sent: list[EmailMessage] = []

    async def fake_send(message: EmailMessage, **_: object) -> None:
        sent.append(message)

    monkeypatch.setattr(email_service.aiosmtplib, "send", fake_send)
    asyncio.run(
        email_service.send_application_notifications(
            "candidate@example.test",
            "Ada\nInjected",
            "Python\r\nBcc: evil@example.test",
            "2026-10-30T03:00:00+00:00",
        )
    )

    assert len(sent) == 2
    assert {message["To"] for message in sent} == {
        "candidate@example.test",
        "admin@example.test",
    }
    for message in sent:
        assert "\r" not in str(message["Subject"])
        assert "\n" not in str(message["Subject"])
        body = message.get_body(preferencelist=("plain",)).get_content()
        assert "CIN" not in body
        assert "password" not in body.casefold()
        assert "Injected" in body


def test_smtp_failure_is_tolerated(monkeypatch: pytest.MonkeyPatch) -> None:
    get_settings().smtp_host = "fake.smtp.test"

    async def failing_send(*_: object, **__: object) -> None:
        raise OSError("fake SMTP failure")

    monkeypatch.setattr(email_service.aiosmtplib, "send", failing_send)
    result = asyncio.run(
        email_service.send_application_notifications(
            "candidate@example.test", "Ada Candidate", "Python", "2026-10-30"
        )
    )
    assert result is None


def test_empty_smtp_host_disables_sending(monkeypatch: pytest.MonkeyPatch) -> None:
    get_settings().smtp_host = ""

    async def unexpected_send(*_: object, **__: object) -> None:
        raise AssertionError("SMTP transport must not be called")

    monkeypatch.setattr(email_service.aiosmtplib, "send", unexpected_send)
    asyncio.run(
        email_service.send_application_notifications(
            "candidate@example.test", "Ada Candidate", "Python", "2026-10-30"
        )
    )


def test_upload_limit_is_consistent_with_environment_and_config() -> None:
    settings = get_settings()
    example = Path(".env.example").read_text(encoding="utf-8")
    configured_value = next(
        line.split("=", 1)[1] for line in example.splitlines() if line.startswith("MAX_UPLOAD_MB=")
    )
    assert str(settings.max_upload_mb) == configured_value
