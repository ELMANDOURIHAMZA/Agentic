"""Seed the academic demo with two jobs and five synthetic applications.

Every generated CV, diploma and CIN is explicitly fictional. Run after applying
Alembic migrations with: python -m scripts.seed_demo_data
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from pathlib import Path

from docx import Document as DocxDocument
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal
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
from app.security.auth import hash_password

DEMO_PASSWORD = "Demo-Candidate-2026!"
DEMO_CANDIDATES = [
    {
        "first_name": "Amina",
        "last_name": "Benali",
        "email": "amina.benali@example.test",
        "job": "Python Backend Engineer",
        "cin_number": "TEST-CIN-00001",
        "birth_date": "1998-04-12",
        "cv": [
            "Amina Benali",
            "Backend developer — 5 years of professional experience",
            "Employer: Societe Fictive Atlas. Position: Python Backend "
            "Developer. Duration: 60 months.",
            "Experience: Python APIs, FastAPI, PostgreSQL, Docker",
            "Education: Master informatique — Universite fictive — 2022",
            "Diplomas: Master informatique — 2022",
            "Skills: Python, FastAPI, PostgreSQL, Docker, Git",
            "Languages: French, English",
        ],
        "diploma_holder": ("Amina", "Benali"),
        "diploma_title": "Master informatique",
        "diploma_year": 2022,
    },
    {
        "first_name": "Youssef",
        "last_name": "Berrada",
        "email": "youssef.berrada@example.test",
        "job": "Python Backend Engineer",
        "cin_number": "TEST-CIN-00002",
        "birth_date": "1997-08-21",
        "cv": [
            "Youssef Berrada",
            "Backend developer — 2 years of professional experience",
            "Employer: Services Numeriques Fictifs. Position: Backend "
            "Developer. Duration: 24 months.",
            "Experience: Python scripts and Flask REST APIs",
            "Education: Licence informatique — Universite fictive — 2021",
            "Diplomas: Licence informatique — 2021",
            "Skills: Python, Flask, SQL, Git",
            "Languages: French",
        ],
        "diploma_holder": ("Youssef", "Berrada"),
        "diploma_title": "Licence informatique",
        "diploma_year": 2021,
    },
    {
        "first_name": "Karim",
        "last_name": "El Idrissi",
        "email": "karim.elidrissi@example.test",
        "job": "Python Backend Engineer",
        "cin_number": "TEST-CIN-00003",
        "birth_date": "2000-02-09",
        "cv": [
            "Karim El Idrissi",
            "Junior web developer — 1 year of experience",
            "Employer: Studio Web Fictif. Position: Junior Web Developer. Duration: 12 months.",
            "Experience: HTML and CSS integration",
            "Education: Licence professionnelle — 2022",
            "Diplomas: Licence professionnelle — 2022",
            "Skills: HTML, CSS, JavaScript",
            "Languages: French, Arabic",
        ],
        "diploma_holder": ("Karim", "El Idrissi"),
        "diploma_title": "Licence professionnelle",
        "diploma_year": 2022,
    },
    {
        "first_name": "Sarah",
        "last_name": "Bennani",
        "email": "sarah.bennani@example.test",
        "job": "Data Analyst",
        "cin_number": "TEST-CIN-00004",
        "birth_date": "1996-11-03",
        "cv": [
            "Sarah Bennani",
            "Data Analyst — 5 years of professional experience",
            "Employer: Laboratoire Data Fictif. Position: Data Analyst. Duration: 60 months.",
            "Experience: SQL reporting, Python analysis, Power BI dashboards",
            "Education: Master data science — Universite fictive — 2021",
            "Diplomas: Master data science — 2021",
            "Skills: SQL, Python, Power BI, Excel, Tableau",
            "Languages: French, English",
        ],
        # Intentional inconsistency: the diploma is issued to another first name.
        "diploma_holder": ("Samira", "Bennani"),
        "diploma_title": "Master data science",
        "diploma_year": 2021,
    },
    {
        "first_name": "Ines",
        "last_name": "Amrani",
        "email": "ines.amrani@example.test",
        "job": "Data Analyst",
        "cin_number": "TEST-CIN-00005",
        "birth_date": "2001-06-16",
        "cv": [
            "Ines Amrani",
            "Junior reporting assistant — 1 year of experience",
            "Employer: Cabinet Analytique Fictif. Position: Reporting "
            "Assistant. Duration: 12 months.",
            "Experience: Excel spreadsheets and basic SQL queries",
            "Education: Licence economie — Universite fictive — 2023",
            "Diplomas: Licence economie — 2023",
            "Skills: Excel, SQL basics",
            "Languages: Arabic, French, English",
            "اللغات: العربية والفرنسية والإنجليزية",
        ],
        "diploma_holder": ("Ines", "Amrani"),
        "diploma_title": "Licence economie",
        "diploma_year": 2023,
    },
]

DEMO_JOBS = [
    {
        "title": "Python Backend Engineer",
        "description": (
            "Develop and maintain backend APIs. The candidate should design "
            "reliable services, work with relational databases and collaborate "
            "with the engineering team."
        ),
        "required_degree": "Master en informatique",
        "required_experience_years": 3,
        "required_skills": ["Python", "FastAPI", "PostgreSQL"],
        "preferred_skills": ["Docker", "Git"],
        "required_certifications": [],
        "languages": ["French", "English"],
        "location": "Agadir (fictif)",
        "other_requirements": "Knowledge of REST APIs and version control.",
    },
    {
        "title": "Data Analyst",
        "description": (
            "Analyse business data, prepare dashboards, write SQL queries and "
            "communicate clear insights to decision makers."
        ),
        "required_degree": "Master data science ou statistiques",
        "required_experience_years": 2,
        "required_skills": ["SQL", "Python", "Power BI"],
        "preferred_skills": ["Tableau"],
        "required_certifications": [],
        "languages": ["French", "English"],
        "location": "Agadir (fictif)",
        "other_requirements": "Data visualization and analytical thinking.",
    },
]


def _write_pdf(path: Path, lines: list[str]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    document = canvas.Canvas(str(path), pagesize=A4)
    _, height = A4
    y = height - 55
    document.setTitle("Document de démonstration fictif")
    document.setFont("Helvetica-Bold", 12)
    document.drawString(48, y, "DOCUMENT DE DEMONSTRATION — 100% FICTIF")
    y -= 28
    document.setFont("Helvetica", 10)
    for line in lines:
        for part in [line[index : index + 95] for index in range(0, len(line), 95)]:
            if y < 55:
                document.showPage()
                document.setFont("Helvetica", 10)
                y = height - 55
            document.drawString(48, y, part)
            y -= 16
    document.save()
    return path.stat().st_size


def _write_docx(path: Path, lines: list[str]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    document = DocxDocument()
    document.add_heading("DOCUMENT DE DEMONSTRATION — 100% FICTIF", level=1)
    for line in lines:
        document.add_paragraph(line)
    document.save(path)
    return path.stat().st_size


def _remove_previous_demo(db: Session) -> None:
    demo_users = list(db.scalars(select(User).where(User.is_demo.is_(True))))
    demo_jobs = list(db.scalars(select(Job).where(Job.is_demo.is_(True))))
    demo_user_ids = [user.id for user in demo_users]
    demo_job_ids = [job.id for job in demo_jobs]

    # Never cascade-delete applications belonging to non-demo users, or demo
    # users' applications to real jobs. Abort before changing anything.
    if demo_job_ids:
        real_applications_on_demo_jobs = list(
            db.scalars(
                select(Application.id)
                .join(User, User.id == Application.candidate_id)
                .where(
                    Application.job_id.in_(demo_job_ids),
                    User.is_demo.is_(False),
                )
            )
        )
        if real_applications_on_demo_jobs:
            raise RuntimeError(
                "Refusing to reset demo jobs: non-demo candidates have applied to them."
            )

    if demo_user_ids:
        demo_users_on_real_jobs = list(
            db.scalars(
                select(Application.id)
                .join(Job, Job.id == Application.job_id)
                .where(
                    Application.candidate_id.in_(demo_user_ids),
                    Job.is_demo.is_(False),
                )
            )
        )
        if demo_users_on_real_jobs:
            raise RuntimeError(
                "Refusing to reset demo accounts: they have applications to non-demo jobs."
            )

    for user in demo_users:
        applications = list(
            db.scalars(select(Application).where(Application.candidate_id == user.id))
        )
        for application in applications:
            for document in application.documents:
                Path(document.stored_path).unlink(missing_ok=True)
            db.delete(application)
        db.delete(user)
    db.flush()
    for job in demo_jobs:
        db.delete(job)
    db.commit()


def seed_demo_data() -> tuple[int, int]:
    settings = get_settings()
    upload_root = Path(settings.upload_dir).resolve()
    upload_root.mkdir(parents=True, exist_ok=True)
    with SessionLocal() as db:
        _remove_previous_demo(db)
        jobs: dict[str, Job] = {}
        for data in DEMO_JOBS:
            job = Job(
                **data,
                status=JobStatus.PUBLISHED,
                published_at=datetime.now(UTC),
                is_demo=True,
            )
            db.add(job)
            jobs[data["title"]] = job
        db.flush()

        shared_password_hash = hash_password(DEMO_PASSWORD)
        for candidate_data in DEMO_CANDIDATES:
            candidate = User(
                first_name=candidate_data["first_name"],
                last_name=candidate_data["last_name"],
                email=candidate_data["email"],
                password_hash=shared_password_hash,
                role=UserRole.CANDIDATE,
                is_demo=True,
            )
            db.add(candidate)
            db.flush()
            job = jobs[candidate_data["job"]]
            application = Application(
                candidate_id=candidate.id,
                job_id=job.id,
                status=ApplicationStatus.PENDING,
            )
            db.add(application)
            db.flush()

            slug = re.sub(
                r"[^a-z0-9]+",
                "-",
                candidate_data["email"].split("@")[0].casefold(),
            ).strip("-")
            diploma_first, diploma_last = candidate_data["diploma_holder"]
            docs = [
                (
                    DocumentType.CV,
                    "cv",
                    [
                        "CV FICTIF — aucune personne réelle",
                        *candidate_data["cv"],
                    ],
                ),
                (
                    DocumentType.DIPLOMA,
                    "diploma",
                    [
                        "DIPLOME UNIVERSITAIRE FICTIF",
                        f"Holder: {diploma_first} {diploma_last}",
                        f"Title: {candidate_data['diploma_title']}",
                        "Institution: Universite fictive de demonstration",
                        f"Graduation year: {candidate_data['diploma_year']}",
                        "This document is synthetic and has no legal value.",
                    ],
                ),
                (
                    DocumentType.CIN,
                    "cin",
                    [
                        "CARTE D'IDENTITE NATIONALE FICTIVE — SANS VALEUR LEGALE",
                        f"First name: {candidate_data['first_name']}",
                        f"Last name: {candidate_data['last_name']}",
                        f"Birth date: {candidate_data['birth_date']}",
                        f"Fictional reference: {candidate_data['cin_number']}",
                        "Synthetic test document. Not an official identity card.",
                    ],
                ),
            ]
            for document_type, label, lines in docs:
                use_docx = (
                    document_type == DocumentType.CV and candidate_data["first_name"] == "Ines"
                )
                extension = ".docx" if use_docx else ".pdf"
                file_path = upload_root / f"demo-{slug}-{uuid.uuid4().hex}-{label}{extension}"
                size = _write_docx(file_path, lines) if use_docx else _write_pdf(file_path, lines)
                mime_type = (
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    if use_docx
                    else "application/pdf"
                )
                db.add(
                    Document(
                        application_id=application.id,
                        document_type=document_type,
                        stored_path=str(file_path),
                        original_name=f"DEMO-{slug}-{label}{extension}",
                        mime_type=mime_type,
                        size_bytes=size,
                    )
                )
        db.commit()
        return len(DEMO_JOBS), len(DEMO_CANDIDATES)


def main() -> None:
    jobs, applications = seed_demo_data()
    print(f"Created {jobs} published demo jobs and {applications} pending demo applications.")
    print(f"Candidate demo password (shared): {DEMO_PASSWORD}")
    print("Every CV, diploma and identity document is fictional and has no legal value.")
    print("No AI workflow was launched. An administrator must click Process manually.")


if __name__ == "__main__":
    main()
