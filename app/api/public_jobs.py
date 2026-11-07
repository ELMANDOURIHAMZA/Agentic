import unicodedata
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Job, JobStatus

router = APIRouter(tags=["public-jobs"])


def _search_value(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char)).casefold()


def _matches(job: Job, term: str) -> bool:
    needle = _search_value(term)
    values = [
        job.title,
        job.description,
        job.location or "",
        *(str(item) for item in job.required_skills),
        *(str(item) for item in job.preferred_skills),
    ]
    return any(needle in _search_value(value) for value in values)


def _public_jobs(db: Session, term: str) -> list[Job]:
    jobs = list(
        db.scalars(
            select(Job)
            .where(Job.status == JobStatus.PUBLISHED, Job.is_template.is_(False))
            .order_by(Job.published_at.desc())
        )
    )
    return [job for job in jobs if not term or _matches(job, term)]


@router.get("/", response_class=HTMLResponse)
def home(
    request: Request,
    q: str = Query(default="", max_length=100),
    page: int = Query(default=1, ge=1),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    page_size = 10
    jobs = _public_jobs(db, q.strip())
    total_pages = max(1, ceil(len(jobs) / page_size))
    page = min(page, total_pages)
    visible_jobs = jobs[(page - 1) * page_size : page * page_size]
    return request.app.state.templates.TemplateResponse(
        request,
        "public/home.html",
        {
            "jobs": visible_jobs,
            "q": q,
            "page": page,
            "total_pages": total_pages,
        },
    )


@router.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_detail(job_id: int, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    job = db.scalar(
        select(Job).where(
            Job.id == job_id,
            Job.status == JobStatus.PUBLISHED,
            Job.is_template.is_(False),
        )
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Offre introuvable")
    return request.app.state.templates.TemplateResponse(
        request, "public/job_detail.html", {"job": job}
    )
