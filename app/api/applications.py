from pathlib import Path
from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
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
from app.security.auth import new_csrf_token
from app.security.dependencies import get_current_user, require_candidate
from app.services.application_state import can_transition
from app.services.document_reader import DocumentReadError, resolve_upload_path
from app.services.document_storage import store_upload
from app.services.email_service import send_application_notifications

router = APIRouter(tags=["applications"])


def _csrf_valid(request: Request, token: str) -> bool:
    return bool(token and token == request.cookies.get("csrf_token"))


def _job_or_404(db: Session, job_id: int) -> Job:
    job = db.scalar(select(Job).where(Job.id == job_id, Job.status == JobStatus.PUBLISHED))
    if job is None:
        raise HTTPException(status_code=404, detail="Offre introuvable")
    return job


def _wizard_response(request: Request, job: Job, error: str | None = None) -> HTMLResponse:
    token = new_csrf_token()
    response = request.app.state.templates.TemplateResponse(
        request, "public/application_wizard.html", {"job": job, "csrf_token": token, "error": error}
    )
    response.set_cookie("csrf_token", token, httponly=False, samesite="lax")
    return response


@router.get("/jobs/{job_id}/apply", response_class=HTMLResponse)
def application_wizard(
    job_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_candidate),
) -> HTMLResponse:
    if user.role != UserRole.CANDIDATE:
        raise HTTPException(status_code=403, detail="Forbidden")
    return _wizard_response(request, _job_or_404(db, job_id))


@router.post("/jobs/{job_id}/apply/confirm", response_class=HTMLResponse, response_model=None)
def confirm_application(
    job_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
    first_name: Annotated[str, Form()],
    last_name: Annotated[str, Form()],
    phone: Annotated[str, Form()],
    cv: Annotated[UploadFile, File()],
    diploma: Annotated[UploadFile, File()],
    cin: Annotated[UploadFile, File()],
    csrf_token: Annotated[str, Form()] = "",
    db: Session = Depends(get_db),
    user: User = Depends(require_candidate),
) -> HTMLResponse | RedirectResponse:
    job = _job_or_404(db, job_id)
    if not _csrf_valid(request, csrf_token):
        return _wizard_response(request, job, "CSRF validation failed.")
    existing = db.scalar(
        select(Application).where(Application.candidate_id == user.id, Application.job_id == job.id)
    )
    if existing is not None:
        return _wizard_response(request, job, "Vous avez déjà candidaté à cette offre.")
    uploads = ((DocumentType.CV, cv), (DocumentType.DIPLOMA, diploma), (DocumentType.CIN, cin))
    written: list[Path] = []
    try:
        user.first_name = first_name.strip()
        user.last_name = last_name.strip()
        user.phone = phone.strip() or None
        application = Application(
            candidate_id=user.id, job_id=job.id, status=ApplicationStatus.SUBMITTED
        )
        db.add(application)
        db.flush()
        for document_type, upload in uploads:
            path, original_name, mime_type, size = store_upload(upload, document_type)
            written.append(path)
            db.add(
                Document(
                    application_id=application.id,
                    document_type=document_type,
                    stored_path=str(path),
                    original_name=original_name,
                    mime_type=mime_type,
                    size_bytes=size,
                )
            )
        if not can_transition(application.status, ApplicationStatus.PENDING):
            raise RuntimeError("Transition de candidature invalide.")
        application.status = ApplicationStatus.PENDING
        db.commit()
    except HTTPException:
        db.rollback()
        for path in written:
            path.unlink(missing_ok=True)
        raise
    except IntegrityError:
        db.rollback()
        for path in written:
            path.unlink(missing_ok=True)
        return _wizard_response(request, job, "Impossible d'enregistrer la candidature.")
    except Exception:
        db.rollback()
        for path in written:
            path.unlink(missing_ok=True)
        raise
    background_tasks.add_task(
        send_application_notifications,
        user.email,
        f"{user.first_name} {user.last_name}",
        job.title,
        application.applied_at.isoformat(),
    )
    return RedirectResponse(f"/jobs/{job.id}/apply/confirmation", status_code=303)


@router.get("/jobs/{job_id}/apply/confirmation", response_class=HTMLResponse)
def confirmation_page(
    job_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_candidate),
) -> HTMLResponse:
    application = db.scalar(
        select(Application).where(Application.job_id == job_id, Application.candidate_id == user.id)
    )
    if application is None:
        raise HTTPException(status_code=404, detail="Candidature introuvable")
    return request.app.state.templates.TemplateResponse(
        request, "public/application_confirmation.html", {"application": application}
    )


@router.get("/documents/{document_id}")
def download_document(
    document_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document introuvable")
    application = db.get(Application, document.application_id)
    if application is None or (user.role != UserRole.ADMIN and application.candidate_id != user.id):
        raise HTTPException(status_code=403, detail="Forbidden")
    try:
        path = resolve_upload_path(document.stored_path)
    except DocumentReadError:
        raise HTTPException(status_code=404, detail="Document introuvable")
    response = FileResponse(
        path,
        media_type=document.mime_type,
        filename=document.original_name,
        headers={"X-Content-Type-Options": "nosniff"},
    )
    return response
