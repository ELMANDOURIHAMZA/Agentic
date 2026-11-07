from pathlib import Path
from shutil import which
from typing import Any

from app.config import get_settings


class DocumentReadError(ValueError):
    """Document absent, vide, corrompu ou illisible."""


def resolve_upload_path(stored_path: str | Path) -> Path:
    root = Path(get_settings().upload_dir).resolve()
    candidate = Path(stored_path)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    if resolved != root and root not in resolved.parents:
        raise DocumentReadError("Le chemin du document est hors de UPLOAD_DIR.")
    if not resolved.is_file():
        raise DocumentReadError("Le document est introuvable.")
    return resolved


def _ensure_text(text: str) -> str:
    cleaned = "\n".join(line.strip() for line in text.splitlines()).strip()
    if not cleaned:
        raise DocumentReadError("Le document est vide ou ne contient aucun texte lisible.")
    return cleaned


def _ocr_languages() -> str:
    """Langues demandées (OCR_LANGUAGES) restreintes à celles réellement installées."""
    wanted = [lang for lang in get_settings().ocr_languages.split("+") if lang]
    try:
        import pytesseract

        installed = set(pytesseract.get_languages(config=""))
    except Exception:
        return "eng"
    usable = [lang for lang in wanted if lang in installed]
    return "+".join(usable) or "eng"


def _ocr_image(image: Any) -> str:
    import pytesseract

    return pytesseract.image_to_string(image, lang=_ocr_languages())


def _ocr_pdf(path: Path) -> str:
    """OCR de repli pour un PDF scanné (aucune couche texte)."""
    if which("tesseract") is None:
        raise DocumentReadError("PDF scanné : OCR indisponible.")
    try:
        import pypdfium2 as pdfium
    except ImportError as exc:
        raise DocumentReadError("PDF scanné : OCR indisponible.") from exc
    try:
        pdf = pdfium.PdfDocument(str(path))
        pages = [
            _ocr_image(pdf[index].render(scale=2.5).to_pil()) for index in range(min(len(pdf), 5))
        ]
    except Exception as exc:
        raise DocumentReadError("Le PDF scanné est illisible.") from exc
    return "\n".join(pages)


def _read_pdf(path: Path) -> str:
    import pdfplumber

    try:
        with pdfplumber.open(path) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception as exc:
        raise DocumentReadError("Le PDF est corrompu ou illisible.") from exc
    if not text.strip():
        text = _ocr_pdf(path)
    return _ensure_text(text)


def _read_docx(path: Path) -> str:
    from docx import Document

    try:
        document = Document(path)
        parts = [paragraph.text for paragraph in document.paragraphs]
        parts.extend(
            cell.text for table in document.tables for row in table.rows for cell in row.cells
        )
    except Exception as exc:
        raise DocumentReadError("Le document DOCX est corrompu ou illisible.") from exc
    return _ensure_text("\n".join(parts))


def _read_image(path: Path) -> str:
    if which("tesseract") is None:
        raise DocumentReadError("OCR indisponible.")
    try:
        import pytesseract  # noqa: F401
        from PIL import Image
    except ImportError as exc:
        raise DocumentReadError("OCR indisponible.") from exc
    try:
        text = _ocr_image(Image.open(path))
    except Exception as exc:
        raise DocumentReadError("L'image est corrompue ou illisible.") from exc
    return _ensure_text(text)


def read_document(stored_path: str | Path) -> str:
    path = resolve_upload_path(stored_path)
    suffix = path.suffix.casefold()
    readers: dict[str, Any] = {
        ".pdf": _read_pdf,
        ".docx": _read_docx,
        ".jpg": _read_image,
        ".jpeg": _read_image,
        ".png": _read_image,
    }
    reader = readers.get(suffix)
    if reader is None:
        raise DocumentReadError(f"Format de document non supporté: {suffix or 'inconnu'}.")
    return reader(path)
