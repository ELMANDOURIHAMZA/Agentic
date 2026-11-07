import json
from uuid import uuid4

from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import (
    AnalysisResult,
    Application,
    ApplicationStatus,
    DocumentVerification,
    Job,
    JobStatus,
    User,
    UserRole,
)
from app.security.auth import hash_password
from app.services.presentation import criterion_label, format_score, review_reasons
from tests.helpers import _admin, _login


def _complete(db, job: Job, name: str, score: float, compliance: float, severity: str | None):
    user = User(
        first_name=name,
        last_name="Test",
        email=f"{uuid4()}@example.test",
        password_hash=hash_password("StrongPassword!123"),
        role=UserRole.CANDIDATE,
    )
    db.add(user)
    db.flush()
    application = Application(
        candidate_id=user.id, job_id=job.id, status=ApplicationStatus.COMPLETED
    )
    db.add(application)
    db.flush()
    inconsistencies = (
        [{"field": "name", "cv_value": "A", "document_value": "B", "severity": severity}]
        if severity
        else []
    )
    db.add(
        DocumentVerification(
            application_id=application.id,
            data={"compliance_level": compliance, "inconsistencies": inconsistencies},
        )
    )
    db.add(
        AnalysisResult(
            application_id=application.id,
            global_score=score,
            score_details={
                "required_skills": {
                    "score": 80,
                    "weight": 40,
                    "justification": "ok",
                    "evidence": [],
                }
            },
            matching_skills=["Python"],
            missing_skills=["Docker"],
            report=json.dumps(
                {
                    "strengths": ["Python"],
                    "gaps": ["Docker"],
                    "conclusion": "Rapport factuel.",
                    "human_decision_reminder": "La décision finale est humaine.",
                }
            ),
        )
    )
    return application.id


def _seed() -> tuple[int, dict[str, int]]:
    with SessionLocal() as db:
        job = Job(
            title="Data Engineer", description="Pipelines de données", status=JobStatus.PUBLISHED
        )
        db.add(job)
        db.flush()
        ids = {
            "low": _complete(db, job, "Bas", 40.0, 95, None),
            "flagged": _complete(db, job, "Alerte", 89.7, 30, "high"),
            "good": _complete(db, job, "Bon", 82.0, 100, None),
        }
        db.commit()
        return job.id, ids


def test_review_rule_flags_low_compliance_and_high_severity() -> None:
    assert review_reasons(None) == []
    assert review_reasons({"compliance_level": 100, "inconsistencies": []}) == []
    assert (
        review_reasons(
            {"compliance_level": 100, "inconsistencies": [{"field": "x", "severity": "low"}]}
        )
        == []
    )
    assert len(review_reasons({"compliance_level": 30, "inconsistencies": []})) == 1
    assert (
        len(
            review_reasons(
                {"compliance_level": 90, "inconsistencies": [{"field": "name", "severity": "high"}]}
            )
        )
        == 1
    )


def test_presentation_helpers() -> None:
    assert criterion_label("documents") == "Cohérence des documents"
    assert criterion_label("inconnu") == "inconnu"
    assert format_score(89.66666) == "89.7"
    assert format_score(None) == "—"


def test_ranking_is_sorted_by_score_and_flags_review() -> None:
    job_id, _ids = _seed()
    client = TestClient(app)
    _login(client, _admin())
    page = client.get(f"/admin/jobs/{job_id}/ranking")
    assert page.status_code == 200
    text = page.text
    assert text.index("Alerte") < text.index("Bon") < text.index("Bas")
    assert "Obligatoire" in text
    assert text.count("Obligatoire") == 1


def test_dashboard_shows_counts_distribution_and_review() -> None:
    _seed()
    client = TestClient(app)
    _login(client, _admin())
    page = client.get("/admin/dashboard")
    assert page.status_code == 200
    assert "Tableau de bord" in page.text
    assert "Data Engineer" in page.text
    assert "70.6" in page.text  # moyenne (40 + 89.7 + 82) / 3


def test_detail_shows_review_banner_labels_and_rounded_scores() -> None:
    _job_id, ids = _seed()
    client = TestClient(app)
    _login(client, _admin())
    page = client.get(f"/admin/applications/{ids['flagged']}")
    assert "Revue humaine obligatoire" in page.text
    assert "Compétences obligatoires" in page.text
    assert "89.7 / 100" in page.text
    assert page.text.count("La décision finale est humaine.") == 1
    ok = client.get(f"/admin/applications/{ids['good']}")
    assert "Revue humaine obligatoire" not in ok.text


def test_report_pdf_export_is_admin_only_and_valid() -> None:
    _job_id, ids = _seed()
    anonymous = TestClient(app)
    assert (
        anonymous.get(
            f"/admin/applications/{ids['good']}/report.pdf", headers={"accept": "application/json"}
        ).status_code
        == 401
    )
    client = TestClient(app)
    _login(client, _admin())
    response = client.get(f"/admin/applications/{ids['flagged']}/report.pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")
    import io

    import pdfplumber

    with pdfplumber.open(io.BytesIO(response.content)) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    assert "REVUE HUMAINE OBLIGATOIRE" in text
    assert "89.7" in text
    assert "Conclusion" in text


def test_candidate_cannot_reach_dashboard_ranking_or_pdf() -> None:
    job_id, ids = _seed()
    with SessionLocal() as db:
        email = f"cand-{uuid4()}@example.test"
        db.add(
            User(
                first_name="C",
                last_name="D",
                email=email,
                password_hash=hash_password("StrongPassword!123"),
                role=UserRole.CANDIDATE,
            )
        )
        db.commit()
    client = TestClient(app)
    _login(client, email)
    for path in (
        "/admin/dashboard",
        f"/admin/jobs/{job_id}/ranking",
        f"/admin/applications/{ids['good']}/report.pdf",
    ):
        assert client.get(path).status_code == 403
