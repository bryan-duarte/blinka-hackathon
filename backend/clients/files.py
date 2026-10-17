from typing import TYPE_CHECKING
from uuid import UUID

from contracts.auth import CurrentUser
from contracts.files import FileParseStatus, FileUploadResult, StoredFile, StoredFileContent

if TYPE_CHECKING:
    from modules.files.service import FilesService


class FilesClient:
    def __init__(self, service: "FilesService") -> None:
        self._service = service

    async def upload(
        self, owner: CurrentUser, filename: str, mime: str, content: bytes
    ) -> FileUploadResult:
        return await self._service.upload(owner, filename, mime, content)

    async def get_context(self, owner: CurrentUser, file_ids: list[UUID]) -> str:
        return await self._service.get_context(owner, file_ids)

    async def get(self, owner: CurrentUser, file_id: UUID) -> StoredFile:
        return await self._service.get(owner, file_id)

    async def read_bytes(self, owner: CurrentUser, file_id: UUID) -> StoredFileContent:
        return await self._service.read_bytes(owner, file_id)

    async def set_parse_status(self, file_id: UUID, status: FileParseStatus) -> None:
        await self._service.set_parse_status(file_id, status)

    async def ensure_bucket(self) -> None:
        await self._service.ensure_bucket()
