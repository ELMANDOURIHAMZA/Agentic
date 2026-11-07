import re
import uuid
from pathlib import Path
from typing import BinaryIO

from fastapi import HTTPException, UploadFile, status

from app.config import get_settings
from app.models.enums import DocumentType

_CHUNK_SIZE = 1024 * 1024
_ALLOWED: dict[DocumentType, dict[str, tuple[str, ...]]] = {
    DocumentType.CV: {
        ".pdf": ("application/pdf",),
        ".docx": (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/zip",
        ),
    },
    DocumentType.DIPLOMA: {
        ".pdf": ("application/pdf",),
        ".docx": (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/zip",
        ),
    },
    DocumentType.CIN: {
        ".pdf": ("application/pdf",),
        ".jpg": ("image/jpeg",),
        ".jpeg": ("image/jpeg",),
        ".png": ("image/png",),
    },
}
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def _magic_matches(extension: str, header: bytes) -> bool:
    if extension == ".pdf":
        return header.startswith(b"%PDF-")
    if extension == ".docx":
        return header.startswith(b"PK\x03\x04")
    if extension in {".jpg", ".jpeg"}:
        return header.startswith(b"\xff\xd8\xff")
    if extension == ".png":
        return header.startswith(b"\x89PNG\r\n\x1a\n")
    return False


def _safe_original_name(name: str | None) -> str:
    cleaned = _SAFE_NAME.sub("_", Path(name or "document").name).strip("._")
    return (cleaned or "document")[:255]


def _validate_metadata(upload: UploadFile, document_type: DocumentType) -> str:
    extension = Path(upload.filename or "").suffix.casefold()
    allowed_mimes = _ALLOWED[document_type].get(extension)
    if not allowed_mimes or upload.content_type not in allowed_mimes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Type de fichier invalide pour {document_type.value}.",
        )
    return extension


def _write_chunks(source: BinaryIO, destination: BinaryIO, max_bytes: int, header: bytes) -> int:
    size = 0
    first_chunk = header
    while True:
        chunk = first_chunk if first_chunk else source.read(_CHUNK_SIZE)
        first_chunk = b""
        if not chunk:
            break
        size += len(chunk)
        if size > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Fichier trop volumineux.",
            )
        destination.write(chunk)
    return size


def store_upload(upload: UploadFile, document_type: DocumentType) -> tuple[Path, str, str, int]:
    extension = _validate_metadata(upload, document_type)
    upload.file.seek(0)
    header = upload.file.read(16)
    if not _magic_matches(extension, header):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La signature du fichier ne correspond pas à son extension.",
        )
    root = Path(get_settings().upload_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    generated = f"{uuid.uuid4().hex}{extension}"
    target = (root / generated).resolve()
    if root not in target.parents:
        raise HTTPException(status_code=400, detail="Chemin de stockage invalide.")
    max_bytes = get_settings().max_upload_mb * 1024 * 1024
    try:
        with target.open("wb") as destination:
            size = _write_chunks(upload.file, destination, max_bytes, header)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return target, _safe_original_name(upload.filename), upload.content_type or "", size
