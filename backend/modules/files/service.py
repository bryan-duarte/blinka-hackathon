import asyncio
from uuid import UUID, uuid4

from contracts.auth import CurrentUser
from contracts.files import FileParseStatus, FileUploadResult, StoredFile, StoredFileContent
from core.logging_config import get_logger
from modules.files import extract
from modules.files.errors import FileMissingError
from modules.files.repository import FilesRepository
from modules.files.storage import StorageBackend

logger = get_logger(__name__)


class FilesService:
    def __init__(self, repository: FilesRepository, storage: StorageBackend) -> None:
        self._repository = repository
        self._storage = storage

    async def upload(
        self, owner: CurrentUser, filename: str, mime: str, content: bytes
    ) -> FileUploadResult:
        resolved_mime = extract.guess_mime(filename, mime)
        storage_key = f"{owner.user_id}/{uuid4()}_{filename}"
        await self._storage.put(storage_key, content, resolved_mime)
        file_id = await self._insert_row_or_discard_upload(
            owner.user_id, filename, resolved_mime, len(content), storage_key
        )
        parse_status = await self._extract_and_record(file_id, filename, resolved_mime, content)
        return FileUploadResult(
            file_id=file_id,
            filename=filename,
            mime=resolved_mime,
            size_bytes=len(content),
            parse_status=parse_status,
        )

    async def get_context(self, owner: CurrentUser, file_ids: list[UUID]) -> str:
        previews = [await self._preview(owner, file_id) for file_id in file_ids]
        return "\n\n".join(previews)

    async def get(self, owner: CurrentUser, file_id: UUID) -> StoredFile:
        stored_file = await self._repository.get(file_id, owner.user_id)
        if stored_file is None:
            raise FileMissingError
        return stored_file

    async def read_bytes(self, owner: CurrentUser, file_id: UUID) -> StoredFileContent:
        stored_file = await self.get(owner, file_id)
        content = await self._storage.get(stored_file.storage_key)
        return StoredFileContent(file=stored_file, content=content)

    async def set_parse_status(self, file_id: UUID, status: FileParseStatus) -> None:
        await self._repository.set_parse_status(file_id, status)

    async def ensure_bucket(self) -> None:
        await self._storage.ensure_bucket()

    async def _preview(self, owner: CurrentUser, file_id: UUID) -> str:
        file_content = await self.read_bytes(owner, file_id)
        filename = file_content.file.filename
        preview = await asyncio.to_thread(
            extract.extract_preview, filename, file_content.file.mime, file_content.content
        )
        if preview is None:
            return f"[file: {filename}] (no text preview available)"
        return f"[file: {filename}]\n{preview}"

    async def _insert_row_or_discard_upload(
        self,
        owner_id: UUID,
        filename: str,
        mime: str,
        size_bytes: int,
        storage_key: str,
    ) -> UUID:
        try:
            return await self._repository.insert(
                owner_id, filename, mime, size_bytes, storage_key, FileParseStatus.PENDING
            )
        except Exception:
            await self._storage.delete(storage_key)
            raise

    async def _extract_and_record(
        self, file_id: UUID, filename: str, mime: str, content: bytes
    ) -> FileParseStatus:
        try:
            preview = await asyncio.to_thread(extract.extract_preview, filename, mime, content)
        except Exception:
            logger.exception("file_preview_failed", file_id=file_id)
            parse_status = FileParseStatus.FAILED
        else:
            has_preview = preview is not None
            parse_status = FileParseStatus.PARSED if has_preview else FileParseStatus.UNSUPPORTED
        await self._repository.set_parse_status(file_id, parse_status)
        return parse_status
