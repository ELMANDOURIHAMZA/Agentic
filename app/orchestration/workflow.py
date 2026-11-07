import asyncio
import hashlib
import json
import logging
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.agents.cv_extraction import CVExtractionAgent, CVExtractionInput
from app.agents.document_verification import (
    DocumentVerificationAgent,
    DocumentVerificationInput,
)
from app.agents.job_requirement import JobRequirementAgent, JobRequirementInput
from app.agents.matching import MatchingAgent, MatchingInput
from app.agents.report import ReportAgent, ReportInput
from app.config import get_settings
from app.models import (
    AnalysisResult,
    Application,
    ApplicationStatus,
    Document,
    DocumentType,
    DocumentVerification,
    ExtractedProfile,
    Job,
    StructuredRequirements,
    WorkflowRun,
    WorkflowStatus,
    WorkflowStepLog,
)
from app.services.application_state import can_transition
from app.services.document_reader import DocumentReadError, read_document
from app.services.llm import LLMClient

logger = logging.getLogger(__name__)
_AGENT_NAMES = ("job_requirements", "cv_extraction", "document_verification", "matching", "report")
_SOURCE_HASH_KEY = "_workflow_source_hash"


class WorkflowError(RuntimeError):
    """Erreur explicite d'exécution du workflow."""


def _now() -> datetime:
    return datetime.now(UTC)


def _safe_error(exc: BaseException) -> str:
    error_names = {
        "DocumentReadError": "Document illisible ou introuvable.",
        "LLMError": "Erreur du fournisseur LLM.",
        "JobRequirementAgentError": "Échec de structuration de l'offre.",
        "CVExtractionAgentError": "Échec d'extraction du CV.",
        "DocumentVerificationAgentError": "Échec de vérification documentaire.",
        "MatchingAgentError": "Échec du matching.",
        "ReportAgentError": "Échec de génération du rapport.",
    }
    return error_names.get(type(exc).__name__, "Échec technique du workflow.")


def _job_source_hash(job: Job) -> str:
    source = {
        "title": job.title,
        "description": job.description,
        "required_degree": job.required_degree,
        "required_experience_years": job.required_experience_years,
        "required_skills": job.required_skills,
        "preferred_skills": job.preferred_skills,
        "required_certifications": job.required_certifications,
        "languages": job.languages,
        "other_requirements": job.other_requirements,
    }
    return hashlib.sha256(
        json.dumps(source, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _application_source_hash(job: Job, application: Application) -> str:
    source = {
        "job": _job_source_hash(job),
        "documents": sorted(
            (document.document_type.value, document.stored_path)
            for document in application.documents
        ),
    }
    return hashlib.sha256(
        json.dumps(source, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _document_for(application: Application, kind: DocumentType) -> Document:
    document = next((item for item in application.documents if item.document_type == kind), None)
    if document is None:
        raise WorkflowError(f"Document {kind.value} manquant.")
    return document


def recover_stale_processing(db: Session) -> int:
    """Récupère les traitements abandonnés (crash, redémarrage) en erreurs relançables.

    Trois cas, tous traités sans double exécution possible :
    1. run ``RUNNING`` plus ancien que le délai : le worker est considéré perdu ;
    2. run ``PENDING`` plus ancien que le délai : la tâche de fond n'a jamais démarré ;
    3. candidature ``PROCESSING`` sans aucun run actif (orphelin) : la transition et la
       création du run sont atomiques (voir ``reserve_processing``), donc cet état ne peut
       venir que d'une donnée antérieure ou d'une interruption : elle est récupérée de suite.
    """
    cutoff = _now() - timedelta(seconds=get_settings().workflow_stale_timeout_seconds)
    recovered: set[int] = set()
    stale_runs = list(
        db.scalars(
            select(WorkflowRun).where(
                ((WorkflowRun.status == WorkflowStatus.RUNNING) & (WorkflowRun.started_at < cutoff))
                | (
                    (WorkflowRun.status == WorkflowStatus.PENDING)
                    & (WorkflowRun.created_at < cutoff)
                )
            )
        )
    )
    for run in stale_runs:
        run.status = WorkflowStatus.ERROR
        run.finished_at = _now()
        recovered.add(run.application_id)
    active_ids = set(
        db.scalars(
            select(WorkflowRun.application_id).where(
                WorkflowRun.status.in_([WorkflowStatus.PENDING, WorkflowStatus.RUNNING])
            )
        )
    )
    orphan_ids = (
        set(
            db.scalars(
                select(Application.id).where(Application.status == ApplicationStatus.PROCESSING)
            )
        )
        - active_ids
    )
    recovered |= orphan_ids
    for application_id in recovered:
        application = db.get(Application, application_id)
        if application is not None and application.status == ApplicationStatus.PROCESSING:
            application.status = ApplicationStatus.ERROR
            application.error_message = "Traitement interrompu ; relance nécessaire."
    if recovered:
        db.commit()
    return len(recovered)


def reserve_processing(db: Session, application: Application) -> WorkflowRun:
    """Passe la candidature en PROCESSING et crée son run PENDING dans la même transaction."""
    if not can_transition(application.status, ApplicationStatus.PROCESSING):
        raise WorkflowError(f"Transition interdite: {application.status.value} vers PROCESSING.")
    application.status = ApplicationStatus.PROCESSING
    application.error_message = None
    run = WorkflowRun(application_id=application.id, status=WorkflowStatus.PENDING)
    db.add(run)
    db.flush()
    return run


class ApplicationWorkflow:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm_client = llm_client or LLMClient()

    def run(self, db: Session, application_id: int, *, prestarted: bool = False) -> WorkflowRun:
        application = db.scalar(select(Application).where(Application.id == application_id))
        if application is None:
            raise WorkflowError("Candidature introuvable.")
        allowed_statuses = {ApplicationStatus.PENDING, ApplicationStatus.ERROR}
        if prestarted:
            allowed_statuses.add(ApplicationStatus.PROCESSING)
        if application.status not in allowed_statuses:
            raise WorkflowError(f"Workflow refusé pour le statut {application.status.value}.")
        job = db.get(Job, application.job_id)
        if job is None:
            if application.status == ApplicationStatus.PROCESSING:
                application.status = ApplicationStatus.ERROR
                application.error_message = "Offre introuvable."
                for run in db.scalars(
                    select(WorkflowRun).where(
                        WorkflowRun.application_id == application.id,
                        WorkflowRun.status == WorkflowStatus.PENDING,
                    )
                ):
                    run.status = WorkflowStatus.ERROR
                    run.finished_at = _now()
                db.commit()
            raise WorkflowError("Offre introuvable.")

        if not prestarted:
            self._transition(application, ApplicationStatus.PROCESSING)
        application.error_message = None
        workflow_run = db.scalar(
            select(WorkflowRun)
            .where(
                WorkflowRun.application_id == application.id,
                WorkflowRun.status == WorkflowStatus.PENDING,
            )
            .order_by(WorkflowRun.id.desc())
        )
        if workflow_run is None:
            workflow_run = WorkflowRun(application_id=application.id)
            db.add(workflow_run)
        workflow_run.status = WorkflowStatus.RUNNING
        workflow_run.started_at = _now()
        db.flush()
        self._mark = workflow_run.started_at
        try:
            requirements, profile = self._run_first_steps(db, application, job, workflow_run)
            verification = self._run_verification(db, application, profile, workflow_run)
            matching = self._run_matching(db, requirements, profile, verification, workflow_run)
            report = self._run_report(
                db, requirements, profile, verification, matching, workflow_run
            )
            self._persist_analysis(db, application, matching, report)
            self._finish_success(db, application, workflow_run)
            return workflow_run
        except Exception as exc:
            self._finish_failure(db, application, workflow_run, exc)
            raise WorkflowError("Le workflow a échoué.") from exc

    def _run_first_steps(
        self,
        db: Session,
        application: Application,
        job: Job,
        workflow_run: WorkflowRun,
    ) -> tuple[Any, Any]:
        existing = db.scalar(
            select(StructuredRequirements).where(StructuredRequirements.job_id == job.id)
        )
        source_hash = _job_source_hash(job)
        source_application_hash = _application_source_hash(job, application)
        existing_profile = db.scalar(
            select(ExtractedProfile).where(ExtractedProfile.application_id == application.id)
        )

        async def run_parallel() -> list[Any]:
            return await asyncio.gather(
                self._requirements_task(job, existing, source_hash),
                self._profile_task(application, existing_profile, source_application_hash),
                return_exceptions=True,
            )

        parallel_start = _now()
        results = asyncio.run(run_parallel())
        requirements_result, profile_result = results
        if isinstance(requirements_result, Exception):
            self._log_step(
                db,
                workflow_run,
                "job_requirements",
                WorkflowStatus.ERROR,
                _safe_error(requirements_result),
                started_at=parallel_start,
            )
        else:
            self._persist_requirements(db, job, requirements_result, source_hash)
            self._log_step(
                db,
                workflow_run,
                "job_requirements",
                WorkflowStatus.COMPLETED,
                started_at=parallel_start,
            )
        if isinstance(profile_result, Exception):
            self._log_step(
                db,
                workflow_run,
                "cv_extraction",
                WorkflowStatus.ERROR,
                _safe_error(profile_result),
                started_at=parallel_start,
            )
        else:
            profile_data = profile_result.model_dump(mode="json", exclude_none=True)
            profile_data[_SOURCE_HASH_KEY] = source_application_hash
            if existing_profile is None:
                db.add(ExtractedProfile(application_id=application.id, data=profile_data))
            else:
                existing_profile.data = profile_data
            self._log_step(
                db,
                workflow_run,
                "cv_extraction",
                WorkflowStatus.COMPLETED,
                started_at=parallel_start,
            )
        if isinstance(requirements_result, Exception):
            raise requirements_result
        if isinstance(profile_result, Exception):
            raise profile_result
        requirements, profile = requirements_result, profile_result
        self._mark = _now()
        db.flush()
        return requirements, profile

    async def _requirements_task(
        self, job: Job, existing: StructuredRequirements | None, source_hash: str
    ) -> Any:
        log = self._step_context("job_requirements")
        if existing and existing.data.get(_SOURCE_HASH_KEY) == source_hash:
            from app.schemas.agent_outputs import StructuredRequirementsOut

            log["output"] = StructuredRequirementsOut.model_validate(
                {key: value for key, value in existing.data.items() if key != _SOURCE_HASH_KEY}
            )
            return log["output"]
        return await asyncio.to_thread(
            JobRequirementAgent(self._llm_client).run,
            JobRequirementInput(
                title=job.title,
                description=job.description,
                required_degree=job.required_degree or "",
                minimum_experience_years=job.required_experience_years,
                required_skills=[str(value) for value in job.required_skills],
                preferred_skills=[str(value) for value in job.preferred_skills],
                required_certifications=[str(value) for value in job.required_certifications],
                languages=[str(value) for value in job.languages],
                other_requirements=job.other_requirements or "",
            ),
        )

    async def _profile_task(
        self,
        application: Application,
        existing: ExtractedProfile | None,
        source_hash: str,
    ) -> Any:
        if existing and existing.data.get(_SOURCE_HASH_KEY) == source_hash:
            from app.schemas.agent_outputs import ExtractedProfileOut

            return ExtractedProfileOut.model_validate(
                {key: value for key, value in existing.data.items() if key != _SOURCE_HASH_KEY}
            )
        document = _document_for(application, DocumentType.CV)
        text = await asyncio.to_thread(read_document, document.stored_path)
        return await asyncio.to_thread(
            CVExtractionAgent(self._llm_client).run,
            CVExtractionInput(cv_text=text),
        )

    def _step_context(self, name: str) -> dict[str, Any]:
        return {"name": name, "started": _now()}

    @staticmethod
    def _persist_requirements(db: Session, job: Job, requirements: Any, source_hash: str) -> None:
        """Enregistre les exigences ; sûr si deux workflows de la même offre se croisent."""
        data = requirements.model_dump(mode="json")
        data[_SOURCE_HASH_KEY] = source_hash
        existing = db.scalar(
            select(StructuredRequirements).where(StructuredRequirements.job_id == job.id)
        )
        if existing is None:
            try:
                with db.begin_nested():  # SAVEPOINT : un conflit n'invalide pas la transaction
                    db.add(StructuredRequirements(job_id=job.id, data=data))
                    db.flush()
                return
            except IntegrityError:
                existing = db.scalar(
                    select(StructuredRequirements).where(StructuredRequirements.job_id == job.id)
                )
        if existing is not None:
            existing.data = data
        db.flush()

    def _run_verification(
        self,
        db: Session,
        application: Application,
        profile: Any,
        workflow_run: WorkflowRun,
    ) -> Any:
        diploma_text, diploma_error = self._read_optional(application, DocumentType.DIPLOMA)
        cin_text, cin_error = self._read_optional(application, DocumentType.CIN)
        try:
            verification = DocumentVerificationAgent(self._llm_client).run(
                DocumentVerificationInput(
                    diploma_text=diploma_text,
                    cin_text=cin_text,
                    cv_profile=profile,
                    diploma_read_error=diploma_error,
                    cin_read_error=cin_error,
                )
            )
            existing = db.scalar(
                select(DocumentVerification).where(
                    DocumentVerification.application_id == application.id
                )
            )
            verification_data = verification.model_dump(mode="json")
            if existing is None:
                db.add(
                    DocumentVerification(
                        application_id=application.id,
                        data=verification_data,
                    )
                )
            else:
                existing.data = verification_data
            db.flush()
            self._log_step(db, workflow_run, "document_verification", WorkflowStatus.COMPLETED)
            return verification
        except Exception as exc:
            self._log_step(
                db,
                workflow_run,
                "document_verification",
                WorkflowStatus.ERROR,
                _safe_error(exc),
            )
            raise

    @staticmethod
    def _read_optional(
        application: Application, kind: DocumentType
    ) -> tuple[str | None, str | None]:
        try:
            return read_document(_document_for(application, kind).stored_path), None
        except (DocumentReadError, WorkflowError) as exc:
            return None, _safe_error(exc)

    def _run_matching(
        self,
        db: Session,
        requirements: Any,
        profile: Any,
        verification: Any,
        workflow_run: WorkflowRun,
    ) -> Any:
        try:
            result = MatchingAgent(self._llm_client).run(
                MatchingInput(
                    requirements=requirements,
                    profile=profile,
                    document_verification=verification,
                )
            )
            self._log_step(db, workflow_run, "matching", WorkflowStatus.COMPLETED)
            return result
        except Exception as exc:
            self._log_step(db, workflow_run, "matching", WorkflowStatus.ERROR, _safe_error(exc))
            raise

    def _run_report(
        self,
        db: Session,
        requirements: Any,
        profile: Any,
        verification: Any,
        matching: Any,
        workflow_run: WorkflowRun,
    ) -> Any:
        try:
            result = ReportAgent(self._llm_client).run(
                ReportInput(
                    requirements=requirements,
                    profile=profile,
                    document_verification=verification,
                    matching=matching,
                )
            )
            self._log_step(db, workflow_run, "report", WorkflowStatus.COMPLETED)
            return result
        except Exception as exc:
            self._log_step(db, workflow_run, "report", WorkflowStatus.ERROR, _safe_error(exc))
            raise

    @staticmethod
    def _persist_analysis(
        db: Session, application: Application, matching: Any, report: Any
    ) -> None:
        db.add(
            AnalysisResult(
                application_id=application.id,
                global_score=matching.global_score,
                score_details={
                    criterion.name: {
                        "score": criterion.score,
                        "weight": criterion.weight,
                        "justification": criterion.justification,
                        "evidence": criterion.evidence,
                    }
                    for criterion in matching.criteria
                },
                matching_skills=matching.matching_skills,
                missing_skills=matching.missing_skills,
                report=report.model_dump_json(),
            )
        )
        db.flush()

    def _log_step(
        self,
        db: Session,
        workflow_run: WorkflowRun,
        agent: str,
        status: WorkflowStatus,
        error: str | None = None,
        started_at: datetime | None = None,
    ) -> None:
        """Trace une étape avec sa vraie durée (début = fin de l'étape précédente)."""
        finished = _now()
        db.add(
            WorkflowStepLog(
                workflow_run_id=workflow_run.id,
                agent=agent,
                status=status,
                started_at=started_at or getattr(self, "_mark", None) or workflow_run.started_at,
                finished_at=finished,
                error_message=error,
            )
        )
        if started_at is None:
            self._mark = finished
        db.flush()

    @staticmethod
    def _transition(application: Application, target: ApplicationStatus) -> None:
        if not can_transition(application.status, target):
            raise WorkflowError(
                f"Transition interdite: {application.status.value} vers {target.value}."
            )
        application.status = target

    def _finish_success(
        self, db: Session, application: Application, workflow_run: WorkflowRun
    ) -> None:
        self._transition(application, ApplicationStatus.COMPLETED)
        workflow_run.status = WorkflowStatus.COMPLETED
        workflow_run.finished_at = _now()
        db.commit()

    def _finish_failure(
        self, db: Session, application: Application, workflow_run: WorkflowRun, exc: BaseException
    ) -> None:
        message = _safe_error(exc)
        application_id, run_id = application.id, workflow_run.id
        if not db.is_active:  # flush échoué : on repart d'une transaction saine
            db.rollback()
        application = db.get(Application, application_id)
        workflow_run = db.get(WorkflowRun, run_id)
        if workflow_run is None:  # run annulé par le rollback : on garde une trace de l'échec
            workflow_run = WorkflowRun(application_id=application_id, started_at=_now())
            db.add(workflow_run)
        application.status = ApplicationStatus.ERROR
        application.error_message = message
        workflow_run.status = WorkflowStatus.ERROR
        workflow_run.finished_at = _now()
        db.commit()


def run_batch(
    application_ids: Iterable[int],
    *,
    session_factory: Any,
    llm_client: LLMClient | None = None,
    prestarted: bool = False,
    max_workers: int | None = None,
) -> dict[int, str]:
    """Traite un lot de candidatures avec une concurrence bornée (WORKFLOW_MAX_CONCURRENCY).

    Chaque candidature utilise sa propre session et son propre workflow : une erreur
    sur l'une n'affecte jamais les autres.
    """
    ids = list(dict.fromkeys(application_ids))
    workers = max(1, min(max_workers or get_settings().workflow_max_concurrency, len(ids) or 1))

    def process(application_id: int) -> tuple[int, str]:
        db = session_factory()
        try:
            ApplicationWorkflow(llm_client).run(db, application_id, prestarted=prestarted)
            return application_id, "completed"
        except WorkflowError:
            return application_id, "error"
        finally:
            db.close()

    if workers == 1:
        return dict(process(application_id) for application_id in ids)
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="workflow") as pool:
        return dict(pool.map(process, ids))
