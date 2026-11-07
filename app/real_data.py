"""Import local de CV vers l'espace de benchmark, sans créer de candidatures."""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from zipfile import BadZipFile, ZipFile

from fastapi import UploadFile
from sqlalchemy import select
from starlette.datastructures import Headers

from app.db import SessionLocal
from app.models import DocumentType, ImportedCandidateProfile, ImportedProfileStatus
from app.services.document_storage import store_upload


@dataclass(frozen=True)
class ImportStats:
    profiles_created: int
    skipped: int


class RealDatasetImportError(RuntimeError):
    """Erreur explicite d'import d'un dataset local."""


def _category(member_name: str) -> str | None:
    parts = PurePosixPath(member_name).parts
    if len(parts) < 2 or parts[-2].casefold() == "data":
        return None
    return parts[-2].strip() or None


def import_archive(
    archive_path: str,
    *,
    limit: int = 100,
    reset: bool = False,
) -> ImportStats:
    """Importe des PDF et conserve leur provenance comme profils de benchmark."""
    if limit < 0:
        raise RealDatasetImportError("La limite d'import doit être positive ou nulle.")
    try:
        archive = ZipFile(archive_path)
    except (OSError, BadZipFile, ValueError) as exc:
        raise RealDatasetImportError("Archive dataset introuvable ou invalide.") from exc

    created = skipped = 0
    source_dataset = Path(archive_path).name
    with archive, SessionLocal() as db:
        if reset:
            for profile in db.scalars(
                select(ImportedCandidateProfile).where(
                    ImportedCandidateProfile.source_dataset == source_dataset
                )
            ):
                Path(profile.stored_path).unlink(missing_ok=True)
                db.delete(profile)
            db.commit()
        known_hashes = set(db.scalars(select(ImportedCandidateProfile.file_hash)))

        members = sorted(
            (
                info
                for info in archive.infolist()
                if not info.is_dir()
                and info.filename.casefold().endswith(".pdf")
                and _category(info.filename) is not None
            ),
            key=lambda info: info.filename,
        )
        if limit:
            members = members[:limit]
        for info in members:
            category = _category(info.filename)
            if category is None:
                skipped += 1
                continue
            with archive.open(info) as source:
                content = source.read()
            file_hash = hashlib.sha256(content).hexdigest()
            if (
                db.scalar(
                    select(ImportedCandidateProfile.id).where(
                        ImportedCandidateProfile.file_hash == file_hash
                    )
                )
                or file_hash in known_hashes
            ):
                skipped += 1
                continue
            upload = UploadFile(
                filename=PurePosixPath(info.filename).name,
                file=io.BytesIO(content),
                headers=Headers({"content-type": "application/pdf"}),
            )
            path, original_name, mime_type, size = store_upload(upload, DocumentType.CV)
            db.add(
                ImportedCandidateProfile(
                    source_dataset=source_dataset,
                    original_filename=info.filename,
                    stored_path=str(path),
                    professional_category=category,
                    extraction_status=ImportedProfileStatus.NOT_EXTRACTED,
                    file_hash=file_hash,
                    provenance={
                        "archive_member": info.filename,
                        "mime_type": mime_type,
                        "size_bytes": size,
                    },
                )
            )
            known_hashes.add(file_hash)
            created += 1
        db.commit()
    return ImportStats(created, skipped)
