import json
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal, get_db
from app.models import (
    AnalysisResult,
    Application,
    ApplicationStatus,
    Document,
    Job,
    User,
    WorkflowRun,
    WorkflowStepLog,
)
from app.orchestration.workflow import recover_stale_processing, run_batch
from app.security.auth import new_csrf_token
from app.security.dependencies import require_admin
from app.services.llm import LLMClient
from app.services.presentation import review_reasons

router = APIRouter(prefix="/admin/applications", tags=["admin-applications"])

STATUS_LABELS = {
    ApplicationStatus.SUBMITTED: "Candidature envoyée",
    ApplicationStatus.PENDING: "En attente de traitement",
    ApplicationStatus.PROCESSING: "En cours de traitement",
    ApplicationStatus.COMPLETED: "Analyse terminée",
    ApplicationStatus.ERROR: "Erreur de traitement",
}


def _csrf_valid(request: Request, token: str) -> bool:
    return bool(token and token == request.cookies.get("csrf_token"))


def _response(
    request: Request,
    template: str,
    context: dict[str, object],
    status_code: int = 200,
) -> HTMLResponse:
    token = new_csrf_token()
    response = request.app.state.templates.TemplateResponse(
        request, template, {**context, "csrf_token": token}, status_code=status_code
    )
    response.set_cookie("csrf_token", token, httponly=False, samesite="lax")
    return response


def build_llm_client() -> LLMClient:
    settings = get_settings()
    if settings.llm_provider.casefold().strip() != "groq":
        raise HTTPException(status_code=503, detail="Fournisseur Groq mal configuré.")
    if not (settings.llm_api_key or "").strip():
        raise HTTPException(status_code=503, detail="Clé API Groq absente.")
    return LLMClient()


def _status_options() -> list[tuple[str, str]]:
    return [(status.value, STATUS_LABELS[status]) for status in ApplicationStatus]


@router.get("", response_class=HTMLResponse)
def list_applications(
    request: Request,
    job_id: int | None = Query(default=None),
    status_filter: ApplicationStatus | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    recover_stale_processing(db)
    page_size = 20
    query = (
        select(Application, User, Job)
        .join(User, User.id == Application.candidate_id)
        .join(Job, Job.id == Application.job_id)
        .order_by(Application.applied_at.desc())
    )
    count_query = select(func.count()).select_from(Application)
    if job_id is not None:
        query = query.where(Application.job_id == job_id)
        count_query = count_query.where(Application.job_id == job_id)
    if status_filter is not None:
        query = query.where(Application.status == status_filter)
        count_query = count_query.where(Application.status == status_filter)
    total = db.scalar(count_query) or 0
    rows = db.execute(query.offset((page - 1) * page_size).limit(page_size)).all()
    items = [
        {
            "application": application,
            "candidate": candidate,
            "job": job,
            "status_label": STATUS_LABELS[application.status],
        }
        for application, candidate, job in rows
    ]
    jobs = list(db.scalars(select(Job).order_by(Job.title)))
    return _response(
        request,
        "admin/applications.html",
        {
            "items": items,
            "jobs": jobs,
            "job_id": job_id,
            "status_filter": status_filter,
            "statuses": _status_options(),
            "page": page,
            "pages": max(1, (total + page_size - 1) // page_size),
            "message": request.query_params.get("message"),
            "error": None,
        },
    )


def _start_selected(
    ids: list[int],
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session,
    csrf_token: str,
) -> RedirectResponse:
    if not _csrf_valid(request, csrf_token):
        raise HTTPException(status_code=403, detail="CSRF validation failed")
    recover_stale_processing(db)
    valid: list[int] = []
    ignored: list[int] = []
    for application_id in dict.fromkeys(ids):
        application = db.execute(
            select(Application).where(Application.id == application_id).with_for_update()
        ).scalar_one_or_none()
        if application is None or application.status not in {
            ApplicationStatus.PENDING,
            ApplicationStatus.ERROR,
        }:
            ignored.append(application_id)
            continue
        application.status = ApplicationStatus.PROCESSING
        application.error_message = None
        valid.append(application_id)
    llm_client = build_llm_client() if valid else None
    db.commit()
    if valid:
        background_tasks.add_task(
            run_batch,
            valid,
            session_factory=SessionLocal,
            llm_client=llm_client,
            prestarted=True,
        )
    parts = []
    if valid:
        parts.append(f"{len(valid)} traitement(s) lancé(s).")
    if ignored:
        parts.append(f"{len(ignored)} candidature(s) ignorée(s), statut invalide.")
    if not parts:
        parts.append("Aucune candidature sélectionnée.")
    return RedirectResponse(f"/admin/applications?message={'+'.join(parts)}", status_code=303)


@router.post("/process")
def process_selected(
    request: Request,
    background_tasks: BackgroundTasks,
    application_ids: Annotated[list[int], Form()] = [],
    csrf_token: Annotated[str, Form()] = "",
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    return _start_selected(application_ids, request, background_tasks, db, csrf_token)


@router.post("/{application_id}/retry")
def retry_application(
    application_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
    csrf_token: Annotated[str, Form()] = "",
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    return _start_selected([application_id], request, background_tasks, db, csrf_token)


@router.get("/{application_id}", response_class=HTMLResponse)
def application_detail(
    application_id: int,
    request: Request,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    row = db.execute(
        select(Application, User, Job)
        .join(User, User.id == Application.candidate_id)
        .join(Job, Job.id == Application.job_id)
        .where(Application.id == application_id)
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Candidature introuvable")
    application, candidate, job = row
    analysis = db.scalar(
        select(AnalysisResult).where(AnalysisResult.application_id == application.id)
    )
    report: dict[str, object] | None = None
    if analysis is not None:
        try:
            report = json.loads(analysis.report)
        except json.JSONDecodeError:
            report = None
    verification = application.document_verification
    runs = list(
        db.scalars(
            select(WorkflowRun)
            .where(WorkflowRun.application_id == application.id)
            .order_by(WorkflowRun.created_at.desc())
        )
    )
    steps = (
        list(
            db.scalars(
                select(WorkflowStepLog)
                .where(WorkflowStepLog.workflow_run_id.in_([run.id for run in runs]))
                .order_by(WorkflowStepLog.started_at)
            )
        )
        if runs
        else []
    )
    documents = list(db.scalars(select(Document).where(Document.application_id == application.id)))
    return _response(
        request,
        "admin/application_detail.html",
        {
            "application": application,
            "candidate": candidate,
            "job": job,
            "analysis": analysis,
            "report": report,
            "verification": verification,
            "documents": documents,
            "steps": steps,
            "review_reasons": review_reasons(verification.data if verification else None),
            "status_label": STATUS_LABELS[application.status],
            "error": None,
        },
    )


@router.get("/{application_id}/status", response_class=JSONResponse)
def application_status(
    application_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> JSONResponse:
    application = db.get(Application, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Candidature introuvable")
    return JSONResponse(
        {
            "id": application.id,
            "status": application.status.value,
            "status_label": STATUS_LABELS[application.status],
            "error_message": application.error_message,
        }
    )
