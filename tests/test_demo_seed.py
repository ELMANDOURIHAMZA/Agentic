from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.config import get_settings
from app.db import SessionLocal
from app.models import (
    Application,
    ApplicationStatus,
    Document,
    DocumentType,
    Job,
    User,
    UserRole,
    WorkflowRun,
)
from app.services.document_reader import read_document
from scripts.seed_demo_data import seed_demo_data


def test_seed_creates_two_jobs_five_pending_applications_and_fifteen_fake_documents(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(get_settings(), "upload_dir", str(tmp_path))

    assert seed_demo_data() == (2, 5)

    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Job).where(Job.is_demo.is_(True))) == 2
        assert db.scalar(select(func.count()).select_from(User).where(User.is_demo.is_(True))) == 5
        assert (
            db.scalar(
                select(func.count())
                .select_from(Application)
                .where(Application.status == ApplicationStatus.PENDING)
            )
            == 5
        )
        assert db.scalar(select(func.count()).select_from(Document)) == 15
        assert (
            db.scalar(
                select(func.count())
                .select_from(Document)
                .where(Document.stored_path.endswith(".docx"))
            )
            == 1
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(Document)
                .where(Document.stored_path.endswith(".pdf"))
            )
            == 14
        )
        assert db.scalar(select(func.count()).select_from(WorkflowRun)) == 0

        sarah = db.scalar(select(User).where(User.email == "sarah.bennani@example.test"))
        assert sarah is not None
        sarah_application = db.scalar(
            select(Application).where(Application.candidate_id == sarah.id)
        )
        assert sarah_application is not None
        diploma = db.scalar(
            select(Document).where(
                Document.application_id == sarah_application.id,
                Document.document_type == DocumentType.DIPLOMA,
            )
        )
        assert diploma is not None
        assert "Samira Bennani" in read_document(diploma.stored_path)

        ines = db.scalar(select(User).where(User.email == "ines.amrani@example.test"))
        assert ines is not None
        ines_application = db.scalar(select(Application).where(Application.candidate_id == ines.id))
        assert ines_application is not None
        cv = db.scalar(
            select(Document).where(
                Document.application_id == ines_application.id,
                Document.document_type == DocumentType.CV,
            )
        )
        assert cv is not None
        assert Path(cv.stored_path).suffix == ".docx"
        assert "العربية" in read_document(cv.stored_path)


def test_demo_seed_refuses_to_delete_real_applicants_from_demo_jobs(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "upload_dir", str(tmp_path))
    seed_demo_data()

    with SessionLocal() as db:
        demo_job = db.scalar(select(Job).where(Job.is_demo.is_(True)))
        assert demo_job is not None
        real_candidate = User(
            first_name="Real",
            last_name="Candidate",
            email="real-candidate@example.test",
            password_hash="not-used-in-this-test",
            role=UserRole.CANDIDATE,
            is_demo=False,
        )
        db.add(real_candidate)
        db.flush()
        application = Application(
            candidate_id=real_candidate.id,
            job_id=demo_job.id,
            status=ApplicationStatus.PENDING,
        )
        db.add(application)
        db.commit()
        real_application_id = application.id

    with pytest.raises(RuntimeError, match="non-demo candidates"):
        seed_demo_data()

    with SessionLocal() as db:
        assert db.get(Application, real_application_id) is not None
        assert db.scalar(select(func.count()).select_from(Job).where(Job.is_demo.is_(True))) == 2
