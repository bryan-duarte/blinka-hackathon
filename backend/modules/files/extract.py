import mimetypes
from io import BytesIO
from pathlib import PurePath

from pypdf import PdfReader

from contracts.files import EVIDENCE_MIME_BY_EXTENSION, PDF_MIME, XML_MIMES

MAX_EXTRACT_CHARS = 20_000
MAX_EXTRACT_PAGES = 20
FALLBACK_MIME = "application/octet-stream"
FALLBACK_TEXT_ENCODING = "latin-1"


def guess_mime(filename: str, claimed_mime: str) -> str:
    evidence_mime = EVIDENCE_MIME_BY_EXTENSION.get(PurePath(filename).suffix.lower())
    if evidence_mime is not None:
        return evidence_mime
    guessed, _ = mimetypes.guess_type(filename)
    return claimed_mime or guessed or FALLBACK_MIME


def extract_preview(filename: str, mime: str, data: bytes) -> str | None:
    if mime == PDF_MIME:
        return _extract_pdf_text(data)
    if mime in XML_MIMES:
        return decode_text(data)[:MAX_EXTRACT_CHARS] or None
    if mime.startswith("text/") or mime == "application/json":
        return data.decode("utf-8", errors="replace")[:MAX_EXTRACT_CHARS]
    return None


def decode_text(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode(FALLBACK_TEXT_ENCODING)


def _extract_pdf_text(data: bytes) -> str | None:
    try:
        reader = PdfReader(BytesIO(data))
    except Exception:
        return None
    pages = reader.pages[:MAX_EXTRACT_PAGES]
    text = "\n".join(page.extract_text() or "" for page in pages)
    has_text_layer = bool(text.strip())
    return text[:MAX_EXTRACT_CHARS] if has_text_layer else None
