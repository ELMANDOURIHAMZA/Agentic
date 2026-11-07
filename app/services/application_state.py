from app.models.enums import ApplicationStatus

_ALLOWED_TRANSITIONS: dict[ApplicationStatus, set[ApplicationStatus]] = {
    ApplicationStatus.SUBMITTED: {ApplicationStatus.PENDING},
    ApplicationStatus.PENDING: {ApplicationStatus.PROCESSING},
    ApplicationStatus.PROCESSING: {
        ApplicationStatus.COMPLETED,
        ApplicationStatus.ERROR,
    },
    ApplicationStatus.ERROR: {ApplicationStatus.PROCESSING},
    ApplicationStatus.COMPLETED: set(),
}


def can_transition(from_status: ApplicationStatus, to_status: ApplicationStatus) -> bool:
    return to_status in _ALLOWED_TRANSITIONS.get(from_status, set())
