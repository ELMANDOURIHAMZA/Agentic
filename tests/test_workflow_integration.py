"""ApplicationWorkflow de bout en bout avec un transport LLM simulé (aucun réseau)."""

import json
import threading
import time
from typing import Any

import httpx
import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models import (
    AnalysisResult,
    Application,
    ApplicationStatus,
    DocumentVerification,
    ExtractedProfile,
    Job,
    StructuredRequirements,
    User,
    WorkflowRun,
    WorkflowStatus,
    WorkflowStepLog,
)
from app.orchestration.workflow import (
    ApplicationWorkflow,
    WorkflowError,
    recover_stale_processing,
    reserve_processing,
    run_batch,
)
from app.seed import seed_demo
from app.services.llm import LLMClient
from tests.llm_fakes import FakeLLM

PASSWORD = "StrongPassword!123"
STEP_OF = {
    "StructuredRequirementsOut": "job_requirements",
    "ExtractedProfileOut": "cv_extraction",
    "VerificationExtractionOut": "document_verification",
    "SemanticEvaluationOut": "matching",
    "ReportOut": "report",
}


@pytest.fixture
def demo(llm_env) -> dict[str, int]:
    """Jeu de démonstration seedé ; retourne {clé candidat: id candidature}."""
    with SessionLocal() as db:
        seed_demo(db, PASSWORD)
        rows = db.execute(
            select(User.email, Application.id).join(
                Application, Application.candidate_id == User.id
            )
        ).all()
    return {email.removesuffix("@example.test"): app_id for email, app_id in rows}


def execute(app_id: int, fake: FakeLLM) -> tuple[Application, str | None]:
    error = None
    with SessionLocal() as db:
        try:
            ApplicationWorkflow(LLMClient(transport=fake)).run(db, app_id)
        except WorkflowError as exc:
            error = str(exc)
    with SessionLocal() as db:
        return db.get(Application, app_id), error


def steps(app_id: int) -> list[tuple[str, WorkflowStatus]]:
    with SessionLocal() as db:
        rows = db.scalars(
            select(WorkflowStepLog)
            .join(WorkflowRun, WorkflowRun.id == WorkflowStepLog.workflow_run_id)
            .where(WorkflowRun.application_id == app_id)
            .order_by(WorkflowStepLog.id)
        )
        return [(row.agent, row.status) for row in rows]


def analysis(app_id: int) -> AnalysisResult:
    with SessionLocal() as db:
        return db.scalar(select(AnalysisResult).where(AnalysisResult.application_id == app_id))


def test_seed_is_idempotent_and_creates_required_dataset(llm_env) -> None:
    with SessionLocal() as db:
        first = seed_demo(db, PASSWORD)
        second = seed_demo(db, PASSWORD)
        assert (first.jobs, first.applications, first.documents) == (2, 5, 15)
        assert (second.users, second.jobs, second.applications, second.documents) == (0, 0, 0, 0)
        statuses = set(db.scalars(select(Application.status)))
        assert statuses == {ApplicationStatus.PENDING}  # aucune analyse automatique
        assert db.scalar(select(Job).where(Job.required_degree.is_(None))) is not None


def test_seed_refuses_weak_password(llm_env) -> None:
    from app.seed import SeedError

    with SessionLocal() as db, pytest.raises(SeedError):
        seed_demo(db, "faible")


def test_full_workflow_perfect_candidate_completes_with_full_score(demo) -> None:
    app_id = demo["amina.benali"]
    fake = FakeLLM()
    application, error = execute(app_id, fake)
    assert error is None and application.status == ApplicationStatus.COMPLETED
    result = analysis(app_id)
    assert result.global_score == 100.0 and result.missing_skills == []
    report = json.loads(result.report)
    assert report["criteria"] and "décision finale" in report["conclusion"]
    # sorties persistées pour chaque agent
    with SessionLocal() as db:
        assert db.scalar(select(ExtractedProfile).where(ExtractedProfile.application_id == app_id))
        assert db.scalar(
            select(DocumentVerification).where(DocumentVerification.application_id == app_id)
        )
        assert db.scalar(select(StructuredRequirements))
    # logs : les cinq agents tracés
    done = {agent for agent, status in steps(app_id) if status == WorkflowStatus.COMPLETED}
    assert done == set(STEP_OF.values())


def test_partial_candidate_gets_partial_score(demo) -> None:
    app_id = demo["youssef.tazi"]
    application, _ = execute(app_id, FakeLLM())
    assert application.status == ApplicationStatus.COMPLETED
    result = analysis(app_id)
    assert 0 < result.global_score < 70
    assert {"FastAPI", "PostgreSQL"} <= set(result.missing_skills)


def test_offer_without_degree_is_analysed(demo) -> None:
    app_id = demo["salma.idrissi"]
    application, error = execute(app_id, FakeLLM())
    assert error is None and application.status == ApplicationStatus.COMPLETED
    result = analysis(app_id)
    assert "degree" not in result.score_details and result.global_score == 100.0
    assert round(sum(v["weight"] for v in result.score_details.values()), 6) == 100


def test_voluntary_inconsistency_is_detected_and_flagged(demo) -> None:
    app_id = demo["karim.alaoui"]
    application, _ = execute(app_id, FakeLLM())
    assert application.status == ApplicationStatus.COMPLETED
    with SessionLocal() as db:
        data = db.scalar(
            select(DocumentVerification).where(DocumentVerification.application_id == app_id)
        ).data
    kinds = {item["kind"] for item in data["inconsistencies"]}
    assert {"diploma_holder", "year"} <= kinds
    assert data["compliance_level"] < 70
    assert "CIN" not in json.dumps(data) and "ZZ000005" not in json.dumps(data)
    assert any("Chraibi" in i for i in json.loads(analysis(app_id).report)["inconsistencies"])


def test_agents_1_and_2_run_in_parallel_and_others_follow_dependencies(demo) -> None:
    fake = FakeLLM()
    fake.barrier = threading.Barrier(2, timeout=5)  # ne passe que si les deux sont simultanés
    application, error = execute(demo["amina.benali"], fake)
    assert error is None and application.status == ApplicationStatus.COMPLETED
    window = {name: (start, end) for name, start, end in fake.calls}
    assert window["VerificationExtractionOut"][0] >= window["ExtractedProfileOut"][1]
    assert window["SemanticEvaluationOut"][0] >= window["VerificationExtractionOut"][1]
    assert window["SemanticEvaluationOut"][0] >= window["StructuredRequirementsOut"][1]
    assert window["ReportOut"][0] >= window["SemanticEvaluationOut"][1]


def test_results_are_transmitted_between_agents(demo) -> None:
    seen: dict[str, Any] = {}

    def spy(request: dict[str, Any]) -> dict[str, Any]:
        seen["input"] = request["input"]
        return FakeLLM.default("ReportOut", request)

    execute(demo["amina.benali"], FakeLLM({"ReportOut": spy}))
    text = seen["input"]
    assert "<matching>" in text and '"global_score":100.0' in text.replace(" ", "")
    assert "Amina" in text and "ZZ000001" not in text and "01/01/1990" not in text


@pytest.mark.parametrize("schema", list(STEP_OF))
def test_agent_failure_sets_error_status_logs_and_allows_retry(demo, schema: str) -> None:
    app_id = demo["amina.benali"]
    application, error = execute(app_id, FakeLLM({schema: RuntimeError("boom")}))
    assert error and application.status == ApplicationStatus.ERROR
    assert application.error_message
    with SessionLocal() as db:
        assert (
            db.scalar(select(AnalysisResult).where(AnalysisResult.application_id == app_id)) is None
        )
    assert (STEP_OF[schema], WorkflowStatus.ERROR) in steps(app_id)
    # relance : de nouveau possible et réussie
    application, error = execute(app_id, FakeLLM())
    assert error is None and application.status == ApplicationStatus.COMPLETED
    assert application.error_message is None
    assert analysis(app_id).global_score == 100.0
    with SessionLocal() as db:
        runs = list(db.scalars(select(WorkflowRun).where(WorkflowRun.application_id == app_id)))
    assert [r.status for r in runs].count(WorkflowStatus.ERROR) == 1  # logs conservés


def test_invalid_json_and_timeout_are_errors_not_silent_success(demo) -> None:
    for app_key, override in (
        ("amina.benali", {"ReportOut": "{pas du json"}),
        ("youssef.tazi", {"SemanticEvaluationOut": httpx.TimeoutException("timeout")}),
    ):
        application, error = execute(demo[app_key], FakeLLM(override))
        assert error and application.status == ApplicationStatus.ERROR


def test_double_execution_is_prevented(demo) -> None:
    app_id = demo["amina.benali"]
    with SessionLocal() as db:
        application = db.get(Application, app_id)
        reserve_processing(db, application)
        db.commit()
    with SessionLocal() as db, pytest.raises(WorkflowError):
        ApplicationWorkflow(LLMClient(transport=FakeLLM())).run(db, app_id)  # déjà PROCESSING
    with SessionLocal() as db, pytest.raises(WorkflowError):
        reserve_processing(db, db.get(Application, app_id))  # transition interdite
    execute_done, _ = execute(demo["youssef.tazi"], FakeLLM())
    with SessionLocal() as db, pytest.raises(WorkflowError):  # COMPLETED : pas de re-analyse
        ApplicationWorkflow(LLMClient(transport=FakeLLM())).run(db, demo["youssef.tazi"])
    assert execute_done.status == ApplicationStatus.COMPLETED


def test_interrupted_processing_is_recovered_in_every_case(demo) -> None:
    from datetime import UTC, datetime, timedelta

    old = datetime.now(UTC) - timedelta(days=2)
    pending_old, orphan, running_old, fresh = (
        demo["amina.benali"],
        demo["youssef.tazi"],
        demo["salma.idrissi"],
        demo["omar.fassi"],
    )
    with SessionLocal() as db:
        for app_id in (pending_old, orphan, running_old, fresh):
            reserve_processing(db, db.get(Application, app_id))
        runs = {r.application_id: r for r in db.scalars(select(WorkflowRun))}
        runs[pending_old].created_at = old  # tâche de fond jamais démarrée
        runs[running_old].status = WorkflowStatus.RUNNING
        runs[running_old].started_at = old  # worker perdu
        db.delete(runs[orphan])  # crash avant création du run (donnée héritée)
        db.commit()
        assert recover_stale_processing(db) == 3
    with SessionLocal() as db:
        for app_id in (pending_old, orphan, running_old):
            application = db.get(Application, app_id)
            assert application.status == ApplicationStatus.ERROR
            assert "relance" in application.error_message
        assert db.get(Application, fresh).status == ApplicationStatus.PROCESSING  # run récent
    application, error = execute(orphan, FakeLLM())  # relançable
    assert error is None and application.status == ApplicationStatus.COMPLETED


def test_batch_runs_with_bounded_parallelism_and_isolates_failures(demo) -> None:
    ids = [demo[k] for k in ("amina.benali", "youssef.tazi", "salma.idrissi", "omar.fassi")]
    with SessionLocal() as db:
        for app_id in ids:
            reserve_processing(db, db.get(Application, app_id))
        db.commit()
    fake = FakeLLM()
    fake.report_delay = 0.2
    failing = demo["omar.fassi"]
    original = fake.__call__

    def selective(provider: str, request: dict[str, Any], timeout: float) -> Any:
        if "Omar" in request["input"] and request["schema"].get("title") == "ReportOut":
            raise RuntimeError("échec isolé")
        return original(provider, request, timeout)

    started = time.monotonic()
    results = run_batch(
        ids,
        session_factory=SessionLocal,
        llm_client=LLMClient(transport=selective),
        prestarted=True,
        max_workers=2,
    )
    elapsed = time.monotonic() - started
    assert results[failing] == "error"
    assert [results[i] for i in ids if i != failing] == ["completed"] * 3
    assert elapsed < 4 * 0.2 + 1.5  # plus rapide qu'un traitement séquentiel pur + marge
    with SessionLocal() as db:
        assert db.get(Application, failing).status == ApplicationStatus.ERROR
