import pytest

from app.models.enums import ApplicationStatus
from app.services.application_state import can_transition


@pytest.mark.parametrize(
    ("from_status", "to_status"),
    [
        (ApplicationStatus.SUBMITTED, ApplicationStatus.PENDING),
        (ApplicationStatus.PENDING, ApplicationStatus.PROCESSING),
        (ApplicationStatus.PROCESSING, ApplicationStatus.COMPLETED),
        (ApplicationStatus.PROCESSING, ApplicationStatus.ERROR),
        (ApplicationStatus.ERROR, ApplicationStatus.PROCESSING),
    ],
)
def test_valid_application_transitions(
    from_status: ApplicationStatus, to_status: ApplicationStatus
) -> None:
    assert can_transition(from_status, to_status)


@pytest.mark.parametrize(
    ("from_status", "to_status"),
    [
        (ApplicationStatus.SUBMITTED, ApplicationStatus.PROCESSING),
        (ApplicationStatus.PENDING, ApplicationStatus.COMPLETED),
        (ApplicationStatus.COMPLETED, ApplicationStatus.ERROR),
        (ApplicationStatus.ERROR, ApplicationStatus.COMPLETED),
    ],
)
def test_invalid_application_transitions(
    from_status: ApplicationStatus, to_status: ApplicationStatus
) -> None:
    assert not can_transition(from_status, to_status)
