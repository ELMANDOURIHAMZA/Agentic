"""Pipeline de benchmark isolé des candidatures réelles."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.cv_extraction import (
    CVExtractionAgent,
    CVExtractionAgentError,
    CVExtractionInput,
)
from app.config import get_settings
from app.models import ImportedCandidateProfile, ImportedProfileStatus
from app.services.document_reader import DocumentReadError, read_document
from app.services.llm import LLMClient


class BenchmarkAnnotation(BaseModel):
    """Vérité terrain fournie explicitement par un annotateur externe."""

    profile_id: int
    fields: dict[str, list[str]] = Field(default_factory=dict)


class BenchmarkMetrics(BaseModel):
    precision: float
    recall: float
    f1_score: float
    annotated_profiles: int


class BenchmarkSummary(BaseModel):
    selected: int
    extracted: int
    extraction_failures: int
    exploitable_rate: float
    metrics: dict[str, BenchmarkMetrics] = Field(default_factory=dict)
    provider: str
    model: str


def _metric(predicted: set[str], expected: set[str], count: int) -> BenchmarkMetrics:
    true_positive = len(predicted & expected)
    precision = true_positive / len(predicted) if predicted else 0.0
    recall = true_positive / len(expected) if expected else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return BenchmarkMetrics(
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1_score=round(f1, 4),
        annotated_profiles=count,
    )


def _values(profile: dict[str, Any], field: str) -> set[str]:
    values = profile.get(field, [])
    if not isinstance(values, list):
        return set()
    return {str(value).strip().casefold() for value in values if str(value).strip()}


def _annotated_metrics(
    results: dict[int, dict[str, Any]],
    annotations: Iterable[BenchmarkAnnotation],
) -> dict[str, BenchmarkMetrics]:
    grouped: dict[str, list[tuple[set[str], set[str]]]] = {}
    for annotation in annotations:
        predicted = results.get(annotation.profile_id)
        if predicted is None:
            continue
        for field, expected_values in annotation.fields.items():
            grouped.setdefault(field, []).append(
                (_values(predicted, field), {value.strip().casefold() for value in expected_values})
            )
    return {
        field: _metric(
            {value for predicted, _ in pairs for value in predicted},
            {value for _, expected in pairs for value in expected},
            len(pairs),
        )
        for field, pairs in grouped.items()
    }


def benchmark_profiles(
    db: Session,
    *,
    profile_ids: Iterable[int] | None = None,
    category: str | None = None,
    limit: int = 100,
    annotations: Iterable[BenchmarkAnnotation] = (),
    llm_client: LLMClient | None = None,
) -> BenchmarkSummary:
    """Extrait des profils importés sans créer de compte, offre ou candidature."""
    if limit < 1:
        raise ValueError("La limite du benchmark doit être positive.")
    query = select(ImportedCandidateProfile).order_by(ImportedCandidateProfile.id)
    if profile_ids is not None:
        ids = list(dict.fromkeys(profile_ids))
        query = query.where(ImportedCandidateProfile.id.in_(ids))
    if category:
        query = query.where(ImportedCandidateProfile.professional_category == category)
    profiles = list(db.scalars(query.limit(limit)))
    client = llm_client or LLMClient()
    settings = get_settings()
    provider = settings.llm_provider.casefold().strip()
    model = settings.llm_model or "non-configure"
    results: dict[int, dict[str, Any]] = {}
    failures = 0
    for profile in profiles:
        benchmark_metadata = {
            "provider": provider,
            "model": model,
            "started_at": datetime.now(UTC).isoformat(),
        }
        profile.provenance = {
            **profile.provenance,
            "benchmark": benchmark_metadata,
        }
        try:
            text = read_document(profile.stored_path)
            profile.extracted_text = text
            extracted = CVExtractionAgent(client).run(CVExtractionInput(cv_text=text))
            payload = extracted.model_dump(mode="json")
            profile.extraction_status = ImportedProfileStatus.EXTRACTED
            results[profile.id] = payload
            profile.provenance = {
                **profile.provenance,
                "benchmark": {
                    **benchmark_metadata,
                    "completed_at": datetime.now(UTC).isoformat(),
                },
                "extraction": payload,
            }
        except (DocumentReadError, CVExtractionAgentError):
            profile.extraction_status = ImportedProfileStatus.EXTRACTION_ERROR
            failures += 1
    db.commit()
    metrics = _annotated_metrics(results, annotations)
    extracted = len(results)
    return BenchmarkSummary(
        selected=len(profiles),
        extracted=extracted,
        extraction_failures=failures,
        exploitable_rate=round(extracted / len(profiles), 4) if profiles else 0.0,
        metrics=metrics,
        provider=provider,
        model=model,
    )
