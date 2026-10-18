import asyncio
from uuid import UUID, uuid4

from contracts.auth import CurrentUser
from contracts.files import (
    SCAN_CLEARED_STATUSES,
    ZIP_MIME,
    EvidenceFileView,
    EvidenceIntake,
    EvidenceIntakeStatus,
    EvidenceLink,
    FileParseStatus,
    FileUploadResult,
    StoredFile,
    StoredFileContent,
    UploadedContent,
)
from contracts.mail_gateway import FetchedAttachment
from core.logging_config import get_logger
from modules.files import archives, evidence, extract
from modules.files.errors import (
    FileMissingError,
    FileQuarantinedError,
    UnsafeArchiveError,
    UnsupportedFileError,
)
from modules.files.repository import FilesRepository
from modules.files.scan import MalwareScanService
from modules.files.storage import StorageBackend

logger = get_logger(__name__)


class FilesService:
    def __init__(
        self, repository: FilesRepository, storage: StorageBackend, scanner: MalwareScanService
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._scanner = scanner

    async def upload(
        self, owner: CurrentUser, filename: str, mime: str, content: bytes
    ) -> FileUploadResult:
        resolved_mime = extract.guess_mime(filename, mime)
        is_fake_archive = resolved_mime == ZIP_MIME and not archives.is_zip(content)
        if is_fake_archive:
            raise UnsupportedFileError("zip content does not match its extension")
        storage_key = f"{owner.user_id}/{uuid4()}_{filename}"
        await self._storage.put(storage_key, content, resolved_mime)
        file_id = await self._insert_row_or_discard_upload(
            owner.user_id, filename, resolved_mime, len(content), storage_key
        )
        scan_status = await self._scanner.wait_for_scan(storage_key)
        await self._repository.set_scan_status(file_id, scan_status)
        if scan_status in SCAN_CLEARED_STATUSES:
            parse_status = await self._extract_and_record(file_id, filename, resolved_mime, content)
        else:
            logger.warning("file_scan_blocked", file_id=file_id, scan_status=scan_status)
            parse_status = FileParseStatus.PENDING
        return FileUploadResult(
            file_id=file_id,
            filename=filename,
            mime=resolved_mime,
            size_bytes=len(content),
            parse_status=parse_status,
            scan_status=scan_status,
        )

    async def ingest_attachments(
        self, owner: CurrentUser, attachments: list[FetchedAttachment]
    ) -> EvidenceIntake:
        if not attachments:
            return EvidenceIntake(status=EvidenceIntakeStatus.READY)
        try:
            uploads = await asyncio.gather(
                *(self._upload_content(owner, attachment) for attachment in attachments)
            )
        except UnsupportedFileError:
            logger.info("attachment_rejected", reason="content does not match extension")
            return EvidenceIntake(status=EvidenceIntakeStatus.UNREADABLE)
        return await self._ingest_uploads(owner, list(uploads))

    async def ingest_stored_file(self, owner: CurrentUser, file_id: UUID) -> EvidenceIntake:
        stored_content = await self.read_bytes(owner, file_id)
        stored_file = stored_content.file
        upload = FileUploadResult(
            file_id=stored_file.file_id,
            filename=stored_file.filename,
            mime=stored_file.mime,
            size_bytes=stored_file.size_bytes,
            parse_status=stored_file.parse_status,
            scan_status=stored_file.scan_status,
        )
        return await self._ingest_uploads(
            owner, [UploadedContent(upload=upload, content=stored_content.content)]
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

    async def read_cleared_bytes(self, owner: CurrentUser, file_id: UUID) -> StoredFileContent:
        stored_file = await self.get(owner, file_id)
        if stored_file.scan_status not in SCAN_CLEARED_STATUSES:
            raise FileQuarantinedError
        content = await self._storage.get(stored_file.storage_key)
        return StoredFileContent(file=stored_file, content=content)

    async def evidence_views(
        self, owner: CurrentUser, links: list[EvidenceLink]
    ) -> list[EvidenceFileView]:
        stored_files = await self._repository.list_owned(
            [link.file_id for link in links], owner.user_id
        )
        files_by_id = {stored_file.file_id: stored_file for stored_file in stored_files}
        return [
            _to_evidence_view(files_by_id[link.file_id], link)
            for link in links
            if link.file_id in files_by_id
        ]

    async def purge_owner_objects(self, owner_id: UUID) -> int:
        deleted_count = await self._storage.delete_prefix(f"{owner_id}/")
        logger.info("owner_objects_purged", owner_id=owner_id, deleted_count=deleted_count)
        return deleted_count

    async def set_parse_status(self, file_id: UUID, status: FileParseStatus) -> None:
        await self._repository.set_parse_status(file_id, status)

    async def _ingest_uploads(
        self, owner: CurrentUser, uploads: list[UploadedContent]
    ) -> EvidenceIntake:
        quarantined = evidence.first_quarantined(uploads)
        if quarantined is not None:
            return evidence.quarantined_intake(quarantined)
        archive_uploads = [uploaded for uploaded in uploads if uploaded.upload.mime == ZIP_MIME]
        documents = [uploaded for uploaded in uploads if uploaded.upload.mime != ZIP_MIME]
        for archive_upload in archive_uploads:
            try:
                members = archives.expand_zip(archive_upload.content)
            except UnsafeArchiveError as archive_error:
                logger.info(
                    "archive_rejected",
                    file_id=archive_upload.upload.file_id,
                    reason=str(archive_error),
                )
                return evidence.unreadable_intake([archive_upload])
            member_uploads = await asyncio.gather(
                *(self._upload_content(owner, member) for member in members)
            )
            quarantined = evidence.first_quarantined(member_uploads)
            if quarantined is not None:
                return evidence.quarantined_intake(quarantined)
            documents.extend(member_uploads)
        return evidence.ready_intake(archive_uploads, documents)

    async def _upload_content(
        self, owner: CurrentUser, attachment: FetchedAttachment
    ) -> UploadedContent:
        upload = await self.upload(owner, attachment.filename, attachment.mime, attachment.content)
        return UploadedContent(upload=upload, content=attachment.content)

    async def _preview(self, owner: CurrentUser, file_id: UUID) -> str:
        stored_file = await self.get(owner, file_id)
        filename = stored_file.filename
        if stored_file.scan_status not in SCAN_CLEARED_STATUSES:
            return f"[file: {filename}] (blocked by the malware scan)"
        content = await self._storage.get(stored_file.storage_key)
        preview = await asyncio.to_thread(
            extract.extract_preview, filename, stored_file.mime, content
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


def _to_evidence_view(stored_file: StoredFile, link: EvidenceLink) -> EvidenceFileView:
    return EvidenceFileView(
        file_id=stored_file.file_id,
        filename=stored_file.filename,
        mime=stored_file.mime,
        size_bytes=stored_file.size_bytes,
        role=link.role,
        scan_status=stored_file.scan_status,
        created_at=stored_file.created_at,
    )
