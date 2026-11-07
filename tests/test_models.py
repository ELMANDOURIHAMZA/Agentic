from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app.db import SessionLocal
from app.models import Application, Job, User, UserRole


def test_create_read_and_unique_constraints() -> None:
    email = f"candidate-{uuid4()}@example.test"
    session = SessionLocal()
    user = User(
        first_name="Ada",
        last_name="Candidate",
        email=email,
        password_hash="fake-development-hash",
        role=UserRole.CANDIDATE,
    )
    job = Job(title="Python Engineer", description="Build APIs")
    session.add_all([user, job])
    session.flush()

    application = Application(candidate_id=user.id, job_id=job.id)
    session.add(application)
    session.commit()

    loaded_user = session.scalar(select(User).where(User.email == email))
    loaded_application = session.scalar(select(Application).where(Application.id == application.id))
    assert loaded_user is not None
    assert loaded_user.first_name == "Ada"
    assert loaded_application is not None
    assert loaded_application.candidate_id == user.id

    duplicate_user = User(
        first_name="Duplicate",
        last_name="Candidate",
        email=email,
        password_hash="fake-development-hash",
    )
    session.add(duplicate_user)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()

    duplicate_application = Application(candidate_id=user.id, job_id=job.id)
    session.add(duplicate_application)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()

    session.execute(delete(Application).where(Application.id == application.id))
    session.execute(delete(User).where(User.id == user.id))
    session.execute(delete(Job).where(Job.id == job.id))
    session.commit()
    session.close()
