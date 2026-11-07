import threading
import time

from app.config import get_settings
from app.orchestration import workflow


def test_run_batch_executes_applications_concurrently(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "workflow_batch_concurrency", 3)
    state_lock = threading.Lock()
    active = 0
    maximum_active = 0

    class DummySession:
        def close(self) -> None:
            pass

    class FakeWorkflow:
        def __init__(self, llm_client=None) -> None:
            pass

        def run(self, db, application_id: int, *, prestarted: bool = False) -> None:
            nonlocal active, maximum_active
            with state_lock:
                active += 1
                maximum_active = max(maximum_active, active)
            time.sleep(0.05)
            with state_lock:
                active -= 1

    monkeypatch.setattr(workflow, "ApplicationWorkflow", FakeWorkflow)

    results = workflow.run_batch(
        [11, 12, 13],
        session_factory=DummySession,
        prestarted=True,
    )

    assert results == {11: "completed", 12: "completed", 13: "completed"}
    assert maximum_active == 3


def test_run_batch_deduplicates_application_ids(monkeypatch) -> None:
    class DummySession:
        def close(self) -> None:
            pass

    processed: list[int] = []

    class FakeWorkflow:
        def __init__(self, llm_client=None) -> None:
            pass

        def run(self, db, application_id: int, *, prestarted: bool = False) -> None:
            processed.append(application_id)

    monkeypatch.setattr(workflow, "ApplicationWorkflow", FakeWorkflow)

    results = workflow.run_batch(
        [7, 7, 8],
        session_factory=DummySession,
    )

    assert results == {7: "completed", 8: "completed"}
    assert sorted(processed) == [7, 8]
