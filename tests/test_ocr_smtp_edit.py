import asyncio
from email import message_from_bytes
from email.header import decode_header, make_header
from shutil import which

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont

from app.config import get_settings
from app.db import SessionLocal
from app.main import app
from app.models import Job, JobStatus
from app.services import document_reader, email_service
from tests.helpers import _admin, _login

needs_tesseract = pytest.mark.skipif(which("tesseract") is None, reason="Tesseract absent")


def _scanned_pdf(path, text: str) -> None:
    """PDF composé uniquement d'une image : aucune couche texte."""
    image = Image.new("RGB", (1400, 400), "white")
    font = ImageFont.load_default(size=60)
    ImageDraw.Draw(image).text((40, 140), text, fill="black", font=font)
    image.save(path, "PDF", resolution=150)


@needs_tesseract
def test_scanned_pdf_is_read_through_ocr(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "upload_dir", str(tmp_path))
    target = tmp_path / "scan.pdf"
    _scanned_pdf(target, "DIPLOMA MASTER COMPUTER SCIENCE")
    text = document_reader.read_document("scan.pdf")
    assert "MASTER" in text.upper()


@needs_tesseract
def test_image_document_is_read_through_ocr(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "upload_dir", str(tmp_path))
    image = Image.new("RGB", (1200, 300), "white")
    ImageDraw.Draw(image).text(
        (30, 100), "IDENTITY CARD", fill="black", font=ImageFont.load_default(size=70)
    )
    image.save(tmp_path / "cin.png")
    assert "IDENTITY" in document_reader.read_document("cin.png").upper()


def test_blank_scanned_pdf_is_reported_unreadable(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "upload_dir", str(tmp_path))
    Image.new("RGB", (600, 300), "white").save(tmp_path / "blank.pdf", "PDF")
    with pytest.raises(document_reader.DocumentReadError):
        document_reader.read_document("blank.pdf")


def test_notifications_are_really_sent_over_smtp(monkeypatch) -> None:
    aiosmtpd = pytest.importorskip("aiosmtpd.controller")
    received: list[bytes] = []

    class Sink:
        async def handle_DATA(self, server, session, envelope):  # noqa: N802
            received.append(envelope.content)
            return "250 OK"

    import socket

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    controller = aiosmtpd.Controller(Sink(), hostname="127.0.0.1", port=port)
    controller.start()
    try:
        settings = get_settings()
        monkeypatch.setattr(settings, "smtp_host", "127.0.0.1")
        monkeypatch.setattr(settings, "smtp_port", port)
        monkeypatch.setattr(settings, "smtp_starttls", False)
        monkeypatch.setattr(settings, "admin_notification_email", "admin@example.test")
        asyncio.run(
            email_service.send_application_notifications(
                "candidate@example.test", "Ada Lovelace", "Data Engineer", "2026-11-01 10:00"
            )
        )
    finally:
        controller.stop()
    assert len(received) == 2
    messages = [message_from_bytes(raw) for raw in received]
    assert {m["To"] for m in messages} == {"candidate@example.test", "admin@example.test"}
    subjects = [str(make_header(decode_header(m["Subject"]))) for m in messages]
    assert subjects == ["Candidature reçue - Data Engineer"] * 2


def test_published_job_can_be_edited_but_closed_job_cannot() -> None:
    with SessionLocal() as db:
        published = Job(
            title="Publiée", description="Description longue", status=JobStatus.PUBLISHED
        )
        closed = Job(title="Clôturée", description="Description longue", status=JobStatus.CLOSED)
        db.add_all([published, closed])
        db.commit()
        published_id, closed_id = published.id, closed.id
    client = TestClient(app)
    _login(client, _admin())
    assert client.get(f"/admin/jobs/{published_id}/edit").status_code == 200
    csrf = client.cookies["csrf_token"]
    form = {"csrf_token": csrf, "title": "Publiée v2", "description": "Nouvelle description"}
    assert (
        client.post(
            f"/admin/jobs/{published_id}/edit", data=form, follow_redirects=False
        ).status_code
        == 303
    )
    with SessionLocal() as db:
        assert db.get(Job, published_id).title == "Publiée v2"
    assert client.get(f"/admin/jobs/{closed_id}/edit").status_code == 409
    assert (
        client.post(f"/admin/jobs/{closed_id}/edit", data=form, follow_redirects=False).status_code
        == 409
    )
