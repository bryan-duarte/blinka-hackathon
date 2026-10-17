from enum import StrEnum
from uuid import UUID

from contracts._base import ApiModel, StrictModel


class FileParseStatus(StrEnum):
    PENDING = "pending"
    PARSED = "parsed"
    FAILED = "failed"
    UNSUPPORTED = "unsupported"


class StoredFile(StrictModel):
    file_id: UUID
    owner_id: UUID
    filename: str
    mime: str
    size_bytes: int
    storage_key: str
    parse_status: FileParseStatus


class StoredFileContent(StrictModel):
    file: StoredFile
    content: bytes


class FileUploadResult(ApiModel):
    file_id: UUID
    filename: str
    mime: str
    size_bytes: int
    parse_status: FileParseStatus
