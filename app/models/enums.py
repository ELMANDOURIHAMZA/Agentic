from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "admin"
    CANDIDATE = "candidate"


class JobStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    CLOSED = "closed"


class ApplicationStatus(StrEnum):
    SUBMITTED = "SUBMITTED"
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"


class DocumentType(StrEnum):
    CV = "CV"
    DIPLOMA = "DIPLOMA"
    CIN = "CIN"


class WorkflowStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"


class ImportedProfileStatus(StrEnum):
    NOT_EXTRACTED = "NOT_EXTRACTED"
    EXTRACTED = "EXTRACTED"
    EXTRACTION_ERROR = "EXTRACTION_ERROR"
    QUARANTINED = "QUARANTINED"
