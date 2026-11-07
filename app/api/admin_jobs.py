from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Job, JobStatus, User
from app.schemas.job import JobCreate
from app.security.auth import csrf_token_for, set_csrf_cookie
from app.security.dependencies import require_admin
from app.services.job_service import close_job, publish_job

router = APIRouter(prefix="/admin/jobs", tags=["admin-jobs"])


def _csrf_is_valid(request: Request, csrf_token: str) -> bool:
    cookie_token = request.cookies.get("csrf_token")
    return bool(cookie_token and csrf_token and cookie_token == csrf_token)


def _csrf_response(request: Request, template: str = "admin/jobs.html") -> HTMLResponse:
    csrf_token = csrf_token_for(request)
    response = request.app.state.templates.TemplateResponse(
        request,
        template,
        {"csrf_token": csrf_token, "error": "CSRF validation failed"},
        status_code=status.HTTP_403_FORBIDDEN,
    )
    set_csrf_cookie(response, csrf_token)
    return response


def _validation_error(exc: ValidationError) -> HTTPException:
    """422 structuré (même format que les validations FastAPI : loc, msg, type)."""
    errors = [
        {"loc": ["body", *map(str, error["loc"])], "msg": error["msg"], "type": error["type"]}
        for error in exc.errors()
    ]
    return HTTPException(status_code=422, detail=errors)


def _form_data(
    title: str,
    description: str,
    required_degree: str,
    required_experience_years: int,
    required_skills: list[str],
    preferred_skills: list[str],
    required_certifications: list[str],
    languages: list[str],
    location: str,
    other_requirements: str,
) -> JobCreate:
    def split_values(values: list[str]) -> list[str]:
        return [part for value in values for part in value.replace(",", "\n").splitlines()]

    return JobCreate(
        title=title,
        description=description,
        required_degree=required_degree or None,
        required_experience_years=required_experience_years,
        required_skills=split_values(required_skills),
        preferred_skills=split_values(preferred_skills),
        required_certifications=split_values(required_certifications),
        languages=split_values(languages),
        location=location or None,
        other_requirements=other_requirements or None,
    )


@router.get("", response_class=HTMLResponse)
def list_jobs(
    request: Request,
    status_filter: JobStatus | None = Query(default=None, alias="status"),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    query = select(Job).order_by(Job.created_at.desc())
    if status_filter:
        query = query.where(Job.status == status_filter)
    jobs = list(db.scalars(query))
    csrf_token = csrf_token_for(request)
    response = request.app.state.templates.TemplateResponse(
        request,
        "admin/jobs.html",
        {"jobs": jobs, "status_filter": status_filter, "csrf_token": csrf_token, "error": None},
    )
    set_csrf_cookie(response, csrf_token)
    return response


@router.post("", response_class=HTMLResponse, response_model=None)
def create_job(
    request: Request,
    title: Annotated[str, Form()],
    description: Annotated[str, Form()],
    required_degree: Annotated[str, Form()] = "",
    required_experience_years: Annotated[int, Form()] = 0,
    required_skills: Annotated[list[str], Form()] = [],
    preferred_skills: Annotated[list[str], Form()] = [],
    required_certifications: Annotated[list[str], Form()] = [],
    languages: Annotated[list[str], Form()] = [],
    location: Annotated[str, Form()] = "",
    other_requirements: Annotated[str, Form()] = "",
    csrf_token: Annotated[str, Form()] = "",
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> RedirectResponse | HTMLResponse:
    if not _csrf_is_valid(request, csrf_token):
        return _csrf_response(request)
    try:
        values = _form_data(
            title,
            description,
            required_degree,
            required_experience_years,
            required_skills,
            preferred_skills,
            required_certifications,
            languages,
            location,
            other_requirements,
        )
    except ValidationError as exc:
        raise _validation_error(exc) from exc
    db.add(Job(**values.model_dump()))
    db.commit()
    return RedirectResponse("/admin/jobs", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{job_id}/edit", response_class=HTMLResponse)
def edit_job(
    job_id: int,
    request: Request,
    title: Annotated[str, Form()],
    description: Annotated[str, Form()],
    required_degree: Annotated[str, Form()] = "",
    required_experience_years: Annotated[int, Form()] = 0,
    required_skills: Annotated[list[str], Form()] = [],
    preferred_skills: Annotated[list[str], Form()] = [],
    required_certifications: Annotated[list[str], Form()] = [],
    languages: Annotated[list[str], Form()] = [],
    location: Annotated[str, Form()] = "",
    other_requirements: Annotated[str, Form()] = "",
    csrf_token: Annotated[str, Form()] = "",
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    if not _csrf_is_valid(request, csrf_token):
        raise HTTPException(status_code=403, detail="CSRF validation failed")
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Offre introuvable")
    if job.status == JobStatus.CLOSED:
        raise HTTPException(status_code=409, detail="Une offre clôturée n'est pas modifiable.")
    try:
        values = _form_data(
            title,
            description,
            required_degree,
            required_experience_years,
            required_skills,
            preferred_skills,
            required_certifications,
            languages,
            location,
            other_requirements,
        )
    except ValidationError as exc:
        raise _validation_error(exc) from exc
    for key, value in values.model_dump().items():
        setattr(job, key, value)
    db.commit()
    return RedirectResponse("/admin/jobs", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/{job_id}/edit", response_class=HTMLResponse)
def edit_job_page(
    job_id: int,
    request: Request,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Offre introuvable")
    if job.status == JobStatus.CLOSED:
        raise HTTPException(status_code=409, detail="Une offre clôturée n'est pas modifiable.")
    csrf_token = csrf_token_for(request)
    response = request.app.state.templates.TemplateResponse(
        request,
        "admin/job_edit.html",
        {"job": job, "csrf_token": csrf_token, "error": None},
    )
    set_csrf_cookie(response, csrf_token)
    return response


def _transition(
    job_id: int, request: Request, csrf_token: str, action: str, db: Session
) -> RedirectResponse:
    if not _csrf_is_valid(request, csrf_token):
        raise HTTPException(status_code=403, detail="CSRF validation failed")
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Offre introuvable")
    if action == "publish":
        publish_job(job)
    else:
        close_job(job)
    db.commit()
    return RedirectResponse("/admin/jobs", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{job_id}/publish")
def publish(
    job_id: int,
    request: Request,
    csrf_token: Annotated[str, Form()] = "",
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    return _transition(job_id, request, csrf_token, "publish", db)


@router.post("/{job_id}/close")
def close(
    job_id: int,
    request: Request,
    csrf_token: Annotated[str, Form()] = "",
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    return _transition(job_id, request, csrf_token, "close", db)
