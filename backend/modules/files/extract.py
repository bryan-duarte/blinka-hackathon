import mimetypes
from io import BytesIO

from pypdf import PdfReader

MAX_EXTRACT_CHARS = 20_000
MAX_EXTRACT_PAGES = 20


def guess_mime(filename: str, claimed_mime: str) -> str:
    guessed, _ = mimetypes.guess_type(filename)
    return claimed_mime or guessed or "application/octet-stream"


def extract_preview(filename: str, mime: str, data: bytes) -> str | None:
    if mime == "application/pdf":
        return _extract_pdf_text(data)
    if mime.startswith("text/") or mime == "application/json":
        return data.decode("utf-8", errors="replace")[:MAX_EXTRACT_CHARS]
    return None


def _extract_pdf_text(data: bytes) -> str | None:
    try:
        reader = PdfReader(BytesIO(data))
    except Exception:
        return None
    pages = reader.pages[:MAX_EXTRACT_PAGES]
    text = "\n".join(page.extract_text() or "" for page in pages)
    return text[:MAX_EXTRACT_CHARS] or None
