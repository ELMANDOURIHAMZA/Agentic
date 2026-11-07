"""Tableau de bord statistique, classement par offre et export PDF (admin)."""

import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.admin_applications import STATUS_LABELS
from app.db import get_db
from app.models import (
    AnalysisResult,
    Application,
    ApplicationStatus,
    ImportedCandidateProfile,
    Job,
    User,
    UserRole,
)
from app.security.auth import new_csrf_token
from app.security.dependencies import require_admin
from app.services.presentation import review_reasons
from app.services.report_pdf import build_report_pdf

router = APIRouter(tags=["admin-dashboard"])

BUCKETS = [(0, 20), (20, 40), (40, 60), (60, 80), (80, 100.01)]


def _page(request: Request, template: str, context: dict[str, object]) -> HTMLResponse:
    token = new_csrf_token()
    response = request.app.state.templates.TemplateResponse(
        request, template, {**context, "csrf_token": token, "error": None}
    )
    response.set_cookie("csrf_token", token, httponly=False, samesite="lax")
    return response


@router.get("/admin/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request, _: User = Depends(require_admin), db: Session = Depends(get_db)
) -> HTMLResponse:
    counted = db.execute(select(Application.status, func.count()).group_by(Application.status))
    by_status = {row[0]: row[1] for row in counted}
    status_counts = [
        {"label": STATUS_LABELS[s], "count": by_status.get(s, 0)} for s in ApplicationStatus
    ]
    total = sum(by_status.values())
    candidate_accounts = (
        db.scalar(
            select(func.count(User.id)).where(
                User.role == UserRole.CANDIDATE, User.is_demo.is_(False)
            )
        )
        or 0
    )
    imported_profiles = db.scalar(select(func.count(ImportedCandidateProfile.id))) or 0
    published_jobs = (
        db.scalar(
            select(func.count(Job.id)).where(Job.status == "published", Job.is_template.is_(False))
        )
        or 0
    )
    scores = list(db.scalars(select(AnalysisResult.global_score)))
    distribution = [
        {"label": f"{low}–{min(int(high), 100)}", "count": sum(low <= v < high for v in scores)}
        for low, high in BUCKETS
    ]
    per_job = []
    for job in db.scalars(select(Job).where(Job.is_template.is_(False)).order_by(Job.title)):
        rows = db.execute(
            select(Application.status, AnalysisResult.global_score)
            .outerjoin(AnalysisResult, AnalysisResult.application_id == Application.id)
            .where(Application.job_id == job.id)
        ).all()
        job_scores = [r[1] for r in rows if r[1] is not None]
        per_job.append(
            {
                "job": job,
                "applications": len(rows),
                "pending": sum(r[0] == ApplicationStatus.PENDING for r in rows),
                "completed": sum(r[0] == ApplicationStatus.COMPLETED for r in rows),
                "errors": sum(r[0] == ApplicationStatus.ERROR for r in rows),
                "average": (sum(job_scores) / len(job_scores)) if job_scores else None,
                "best": max(job_scores) if job_scores else None,
            }
        )
    verifications = db.execute(
        select(Application.id).where(Application.status == ApplicationStatus.COMPLETED)
    ).all()
    review_count = 0
    for (application_id,) in verifications:
        application = db.get(Application, application_id)
        verification = application.document_verification if application else None
        if review_reasons(verification.data if verification else None):
            review_count += 1
    return _page(
        request,
        "admin/dashboard.html",
        {
            "total": total,
            "status_counts": status_counts,
            "average": (sum(scores) / len(scores)) if scores else None,
            "distribution": distribution,
            "max_bucket": max([b["count"] for b in distribution] + [1]),
            "per_job": per_job,
            "review_count": review_count,
            "candidate_accounts": candidate_accounts,
            "imported_profiles": imported_profiles,
            "published_jobs": published_jobs,
        },
    )


@router.get("/admin/jobs/{job_id}/ranking", response_class=HTMLResponse)
def ranking(
    job_id: int,
    request: Request,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Offre introuvable")
    rows = db.execute(
        select(Application, User, AnalysisResult)
        .join(User, User.id == Application.candidate_id)
        .join(AnalysisResult, AnalysisResult.application_id == Application.id)
        .where(Application.job_id == job_id, Application.status == ApplicationStatus.COMPLETED)
        .order_by(AnalysisResult.global_score.desc(), Application.applied_at)
    ).all()
    items = []
    for position, (application, candidate, analysis) in enumerate(rows, start=1):
        verification = application.document_verification
        items.append(
            {
                "rank": position,
                "application": application,
                "candidate": candidate,
                "analysis": analysis,
                "compliance": verification.data.get("compliance_level") if verification else None,
                "reasons": review_reasons(verification.data if verification else None),
            }
        )
    waiting = db.scalar(
        select(func.count())
        .select_from(Application)
        .where(Application.job_id == job_id, Application.status != ApplicationStatus.COMPLETED)
    )
    return _page(
        request, "admin/ranking.html", {"job": job, "items": items, "waiting": waiting or 0}
    )


@router.get("/admin/applications/{application_id}/report.pdf")
def report_pdf(
    application_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Response:
    application = db.get(Application, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Candidature introuvable")
    analysis = application.analysis_result
    if analysis is None:
        raise HTTPException(
            status_code=409, detail="Aucune analyse terminée pour cette candidature."
        )
    candidate = db.get(User, application.candidate_id)
    job = db.get(Job, application.job_id)
    try:
        report = json.loads(analysis.report)
    except json.JSONDecodeError:
        report = None
    verification = application.document_verification
    data = verification.data if verification else None
    pdf = build_report_pdf(
        candidate_name=f"{candidate.first_name} {candidate.last_name}" if candidate else "?",
        job_title=job.title if job else "?",
        status_label=STATUS_LABELS[application.status],
        global_score=analysis.global_score,
        score_details=analysis.score_details,
        matching_skills=[str(v) for v in analysis.matching_skills],
        missing_skills=[str(v) for v in analysis.missing_skills],
        verification=data,
        report=report,
        review_reasons=review_reasons(data),
        generated_at=datetime.now(UTC),
    )
    filename = f"rapport-candidature-{application.id}.pdf"
    return Response(
        pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
