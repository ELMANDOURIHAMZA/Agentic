"""Seed idempotent du jeu de démonstration fictif (2 offres, 5 candidats, 15 documents)."""

from __future__ import annotations

import io
import os
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.datastructures import Headers

from app.demo_data import CANDIDATES, JOBS, documents_for
from app.models import (
    Application,
    ApplicationStatus,
    Document,
    DocumentType,
    Job,
    JobStatus,
    User,
    UserRole,
)
from app.security.auth import hash_password, validate_password_strength
from app.services.document_storage import store_upload

DEMO_ADMIN_EMAIL = "admin.demo@example.test"
_TYPES = {
    "cv": DocumentType.CV,
    "diploma": DocumentType.DIPLOMA,
    "cin": DocumentType.CIN,
}


class SeedError(RuntimeError):
    """Configuration de seed invalide."""


@dataclass
class SeedReport:
    users: int = 0
    jobs: int = 0
    applications: int = 0
    documents: int = 0


def _upload(name: str, content: bytes) -> UploadFile:
    return UploadFile(
        filename=name,
        file=io.BytesIO(content),
        headers=Headers({"content-type": "application/pdf"}),
    )


def seed_demo(db: Session, password: str | None = None) -> SeedReport:
    """Crée les données manquantes uniquement ; relancer ne duplique rien.

    Les candidatures restent ``PENDING`` : aucune analyse IA n'est lancée ici.
    """
    password = password or os.getenv("SEED_PASSWORD", "")
    if not validate_password_strength(password):
        raise SeedError(
            "SEED_PASSWORD requis : 12 caractères minimum avec majuscule, minuscule, "
            "chiffre et symbole (jamais versionné)."
        )
    report = SeedReport()
    password_hash = hash_password(password)

    def ensure_user(email: str, first: str, last: str, role: UserRole, phone: str | None) -> User:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(
                first_name=first,
                last_name=last,
                email=email,
                password_hash=password_hash,
                role=role,
                phone=phone,
                is_demo=True,
            )
            db.add(user)
            db.flush()
            report.users += 1
        return user

    ensure_user(DEMO_ADMIN_EMAIL, "Admin", "Démo", UserRole.ADMIN, None)
    jobs: dict[str, Job] = {}
    for spec in JOBS:
        job = db.scalar(select(Job).where(Job.title == spec.title, Job.is_demo.is_(True)))
        if job is None:
            from datetime import UTC, datetime

            job = Job(
                title=spec.title,
                description=spec.description,
                required_degree=spec.required_degree or None,
                required_experience_years=spec.required_experience_years,
                required_skills=spec.required_skills,
                preferred_skills=spec.preferred_skills,
                languages=spec.languages,
                location=spec.location,
                other_requirements=spec.other_requirements or None,
                status=JobStatus.PUBLISHED,
                published_at=datetime.now(UTC),
                is_demo=True,
            )
            db.add(job)
            db.flush()
            report.jobs += 1
        jobs[spec.key] = job

    for candidate in CANDIDATES:
        user = ensure_user(
            candidate.email,
            candidate.first_name,
            candidate.last_name,
            UserRole.CANDIDATE,
            candidate.phone,
        )
        job = jobs[candidate.job_key]
        application = db.scalar(
            select(Application).where(
                Application.candidate_id == user.id, Application.job_id == job.id
            )
        )
        if application is not None:
            continue
        application = Application(
            candidate_id=user.id, job_id=job.id, status=ApplicationStatus.PENDING
        )
        db.add(application)
        db.flush()
        report.applications += 1
        for key, content in documents_for(candidate).items():
            path, original, mime, size = store_upload(
                _upload(f"{candidate.key}-{key}.pdf", content), _TYPES[key]
            )
            db.add(
                Document(
                    application_id=application.id,
                    document_type=_TYPES[key],
                    stored_path=str(path),
                    original_name=original,
                    mime_type=mime,
                    size_bytes=size,
                )
            )
            report.documents += 1
    db.commit()
    return report


def write_fixtures(target: Path) -> list[Path]:
    """Écrit les PDF fictifs dans ``target`` (versionnables : ils ne contiennent rien de réel)."""
    written: list[Path] = []
    for candidate in CANDIDATES:
        folder = target / candidate.key
        folder.mkdir(parents=True, exist_ok=True)
        for key, content in documents_for(candidate).items():
            path = folder / f"{key}.pdf"
            path.write_bytes(content)
            written.append(path)
    return written
