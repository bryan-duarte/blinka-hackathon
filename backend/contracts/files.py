from datetime import datetime
from enum import StrEnum
from uuid import UUID

from contracts._base import ApiModel, StrictModel

PDF_MIME = "application/pdf"
ZIP_MIME = "application/zip"
XML_MIME = "application/xml"
XML_MIMES = frozenset({XML_MIME, "text/xml"})
EVIDENCE_MIME_BY_EXTENSION = {".pdf": PDF_MIME, ".zip": ZIP_MIME, ".xml": XML_MIME}


class FileParseStatus(StrEnum):
    PENDING = "pending"
    PARSED = "parsed"
    FAILED = "failed"
    UNSUPPORTED = "unsupported"


class FileScanStatus(StrEnum):
    PENDING = "pending"
    CLEAN = "clean"
    THREAT = "threat"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"
    DISABLED = "disabled"


SCAN_CLEARED_STATUSES = frozenset(
    {FileScanStatus.CLEAN, FileScanStatus.UNSUPPORTED, FileScanStatus.DISABLED}
)


class EvidenceRole(StrEnum):
    ARCHIVE = "archive"
    PRIMARY = "primary"
    SECONDARY = "secondary"


class StoredFile(StrictModel):
    file_id: UUID
    owner_id: UUID
    filename: str
    mime: str
    size_bytes: int
    storage_key: str
    parse_status: FileParseStatus
    scan_status: FileScanStatus
    created_at: datetime


class StoredFileContent(StrictModel):
    file: StoredFile
    content: bytes


class FileUploadResult(ApiModel):
    file_id: UUID
    filename: str
    mime: str
    size_bytes: int
    parse_status: FileParseStatus
    scan_status: FileScanStatus


class UploadedContent(StrictModel):
    upload: FileUploadResult
    content: bytes


class EvidenceLink(StrictModel):
    file_id: UUID
    role: EvidenceRole


class EvidenceIntakeStatus(StrEnum):
    READY = "ready"
    MALWARE = "malware"
    SCAN_FAILED = "scan_failed"
    UNREADABLE = "unreadable"


class EvidenceIntake(StrictModel):
    status: EvidenceIntakeStatus
    evidence: list[EvidenceLink] = []
    primary_file_id: UUID | None = None
    primary_sha256: str | None = None
    flagged_file_id: UUID | None = None


class EvidenceFileView(ApiModel):
    file_id: UUID
    filename: str
    mime: str
    size_bytes: int
    role: EvidenceRole
    scan_status: FileScanStatus
    created_at: datetime
