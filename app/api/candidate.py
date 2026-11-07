from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import (
    AnalysisResult,
    Application,
    ApplicationStatus,
    Document,
    DocumentVerification,
    Job,
    User,
)
from app.schemas.candidate import (
    CandidateApplicationView,
    CandidateProfileUpdate,
    build_candidate_view,
)
from app.security.auth import csrf_token_for, set_csrf_cookie
from app.security.dependencies import require_candidate

router = APIRouter(prefix="/candidate", tags=["candidate"])

STATUS_LABELS = {
    ApplicationStatus.SUBMITTED: "Candidature envoyée",
    ApplicationStatus.PENDING: "En attente de traitement",
    ApplicationStatus.PROCESSING: "En cours de traitement",
    ApplicationStatus.COMPLETED: "Analyse terminée",
    ApplicationStatus.ERROR: "Erreur de traitement",
}


def _csrf_valid(request: Request, token: str) -> bool:
    return bool(token and token == request.cookies.get("csrf_token"))


def _page(
    request: Request, template: str, error: str | None = None, **context: object
) -> HTMLResponse:
    token = csrf_token_for(request)
    response = request.app.state.templates.TemplateResponse(
        request, template, {**context, "csrf_token": token, "error": error}
    )
    set_csrf_cookie(response, token)
    return response


def _candidate_application(
    db: Session, application_id: int, user_id: int
) -> tuple[Application, Job]:
    result = db.execute(
        select(Application, Job)
        .join(Job, Job.id == Application.job_id)
        .where(Application.id == application_id, Application.candidate_id == user_id)
    ).first()
    if result is None:
        raise HTTPException(status_code=404, detail="Candidature introuvable")
    return result


@router.get("", response_class=HTMLResponse)
def candidate_home(
    request: Request,
    user: User = Depends(require_candidate),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    return _page(request, "candidate/home.html", user=user)


@router.get("/profile", response_class=HTMLResponse)
def profile(request: Request, user: User = Depends(require_candidate)) -> HTMLResponse:
    return _page(request, "candidate/profile.html", user=user)


@router.post("/profile", response_class=HTMLResponse)
def update_profile(
    request: Request,
    first_name: Annotated[str, Form()],
    last_name: Annotated[str, Form()],
    phone: Annotated[str, Form()] = "",
    csrf_token: Annotated[str, Form()] = "",
    user: User = Depends(require_candidate),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    if not _csrf_valid(request, csrf_token):
        response = _page(
            request, "candidate/profile.html", user=user, error="CSRF validation failed."
        )
        response.status_code = status.HTTP_403_FORBIDDEN
        return response
    try:
        values = CandidateProfileUpdate(first_name=first_name, last_name=last_name, phone=phone)
    except ValueError:
        return _page(request, "candidate/profile.html", user=user, error="Profil invalide.")
    user.first_name = values.first_name
    user.last_name = values.last_name
    user.phone = values.phone
    db.commit()
    return RedirectResponse("/candidate/profile", status_code=303)


@router.get("/applications", response_class=HTMLResponse)
def applications(
    request: Request,
    user: User = Depends(require_candidate),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    rows = db.execute(
        select(Application, Job)
        .join(Job, Job.id == Application.job_id)
        .where(Application.candidate_id == user.id)
        .order_by(Application.applied_at.desc())
    ).all()
    views = [
        CandidateApplicationView(
            id=application.id,
            job_title=job.title,
            applied_at=application.applied_at,
            status=application.status,
            status_label=STATUS_LABELS[application.status],
        )
        for application, job in rows
    ]
    return _page(request, "candidate/applications.html", applications=views, user=user)


@router.get("/applications/{application_id}", response_class=HTMLResponse)
def application_detail(
    application_id: int,
    request: Request,
    user: User = Depends(require_candidate),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    application, job = _candidate_application(db, application_id, user.id)
    documents = list(db.scalars(select(Document).where(Document.application_id == application.id)))
    return _page(
        request,
        "candidate/application_detail.html",
        application=application,
        job=job,
        documents=documents,
        status_label=STATUS_LABELS[application.status],
    )


@router.get("/applications/{application_id}/result", response_class=HTMLResponse)
def application_result(
    application_id: int,
    request: Request,
    user: User = Depends(require_candidate),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    application, _ = _candidate_application(db, application_id, user.id)
    if application.status != ApplicationStatus.COMPLETED:
        return _page(
            request,
            "candidate/result.html",
            result=None,
            message="Les résultats seront disponibles lorsque l'analyse sera terminée.",
        )
    analysis = db.scalar(
        select(AnalysisResult).where(AnalysisResult.application_id == application.id)
    )
    if analysis is None:
        return _page(
            request,
            "candidate/result.html",
            result=None,
            message="Les résultats ne sont pas encore disponibles.",
        )
    verification = db.scalar(
        select(DocumentVerification).where(DocumentVerification.application_id == application.id)
    )
    data = verification.data if verification else {}
    level = data.get("compliance_level")
    result = build_candidate_view(
        global_score=analysis.global_score,
        matching_skills=[str(value) for value in analysis.matching_skills],
        missing_skills=[str(value) for value in analysis.missing_skills],
        compliance_level=float(level) if isinstance(level, int | float) else None,
        has_inconsistencies=bool(data.get("inconsistencies")),
    )
    return _page(request, "candidate/result.html", result=result, message=None)
