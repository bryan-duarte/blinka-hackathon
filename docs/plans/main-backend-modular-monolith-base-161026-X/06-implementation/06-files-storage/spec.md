# Files & Storage

## Overview

Generic file upload (any format) → S3-compatible storage + metadata in PG-1; extraction to agent context. Provider-agnostic: MinIO now, AWS S3 later.

## Files to Create

- `backend/modules/files/__init__.py` — facade: `FilesService`, `FileNotFoundError` (module-scoped, do NOT shadow stdlib — name it `FileMissingError`), `StorageError`
- `backend/modules/files/storage.py`:

```python
class StorageBackend(Protocol):
    async def put(self, key: str, data: bytes, content_type: str) -> None: ...
    async def get(self, key: str) -> bytes: ...
    async def delete(self, key: str) -> None: ...
    async def ensure_bucket(self) -> None: ...

class S3StorageBackend:            # aioboto3; endpoint_url from settings → MinIO or AWS alike
    def __init__(self, endpoint_url: str, bucket: str, access_key_id: str, secret_access_key: str) -> None: ...
```

`ensure_bucket`: `head_bucket` → on 404 `create_bucket` catching `BucketAlreadyOwnedByYou`. Client session created per-service (one aioboto3 `Session`, client reused).

- `backend/modules/files/extract.py` — `extract_preview(filename: str, mime: str, data: bytes) -> str | None`:
  - `application/pdf` → pypdf text of first N pages (constant `MAX_EXTRACT_CHARS = 20_000`)
  - `text/*`, `application/json` → utf-8 decode (errors="replace")
  - images → `None` (kept as multimodal reference only)
  - else → `None`
- `backend/modules/files/models.py` — `FileRecord(ProductBase)` per 03-design.md.
- `backend/modules/files/repository.py` — `FilesRepository(sessionmaker: async_sessionmaker[AsyncSession])`, SQLAlchemy `select()`/`insert()` semantics:
  - `insert(owner_id, filename, mime, size_bytes, storage_key, parse_status) -> UUID`
  - `get(file_id, owner_id) -> FileRow | None` (owner filter — see risks)
  - `set_parse_status(file_id, status) -> None`
- `backend/modules/files/service.py` — `FilesService(repo, storage)`:
  - `async upload(owner: CurrentUser, filename: str, mime: str, data: bytes) -> FileUploadResult`
    - `storage_key = f"{owner.user_id}/{uuid4()}_{filename}"`
    - storage put → row insert → try `extract_preview` → `set_parse_status(parsed|unsupported)` (extraction failure → `failed`, never fails the upload)
  - `async get_context(owner: CurrentUser, file_ids: list[UUID]) -> str`
    - concatenated text for the agent: per file `"[file: {filename}]\n{preview}"`; missing/foreign id → `FileMissingError`
  - `async read_bytes(owner, file_id) -> tuple[FileRow, bytes]` (for invoice parsing)
- `backend/api/routers/files.py` — `files_router = APIRouter(prefix="/files", tags=["files"])`; `POST /files` multipart (`UploadFile`, `File` — FastAPI usage stays in routers) → 201 `FileUploadResult`; size cap `MAX_UPLOAD_BYTES = 25 MB` → 413.
- `backend/clients/files.py` — `FilesClient` with `upload`, `get_context`, `read_bytes` mirroring service.
- `contracts/files.py` — per 03-design.md.

## Implementation Guidelines

- Never trust client mime; derive from filename where ambiguous (`mimetypes.guess_type`).
- Upload path is one logical operation but two systems (S3 + PG): on storage failure → 503 `StorageError`; on DB failure after put → best-effort `delete` then 500.
- `python-multipart` required for `UploadFile` (already in deps).

## Dependencies

02-backend-skeleton, 04-persistence-alembic (files table), 03-docker-stack (MinIO).

## Integration Notes

`get_context` output shape is the file-context contract for orchestrator chat input. `read_bytes` + `parse_status` is what `invoice_ingestor` consumes. `ensure_bucket` is called once in lifespan.
