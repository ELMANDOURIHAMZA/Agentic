from datetime import UTC, datetime

from fastapi import HTTPException, status

from app.models import Job, JobStatus


def publish_job(job: Job) -> None:
    if job.is_template:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un modèle importé doit être repris dans une vraie offre.",
        )
    if job.status != JobStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Seule une offre brouillon peut être publiée.",
        )
    job.status = JobStatus.PUBLISHED
    job.published_at = datetime.now(UTC)


def close_job(job: Job) -> None:
    if job.status != JobStatus.PUBLISHED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Seule une offre publiée peut être clôturée.",
        )
    job.status = JobStatus.CLOSED
    job.closed_at = datetime.now(UTC)
