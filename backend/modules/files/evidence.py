from hashlib import sha256

from contracts.files import (
    PDF_MIME,
    SCAN_CLEARED_STATUSES,
    XML_MIMES,
    EvidenceIntake,
    EvidenceIntakeStatus,
    EvidenceLink,
    EvidenceRole,
    FileScanStatus,
    UploadedContent,
)

XML_PRIMARY_RANK = 0
PDF_PRIMARY_RANK = 1
OTHER_PRIMARY_RANK = 2


def first_quarantined(uploads: list[UploadedContent]) -> UploadedContent | None:
    return next(
        (
            uploaded
            for uploaded in uploads
            if uploaded.upload.scan_status not in SCAN_CLEARED_STATUSES
        ),
        None,
    )


def select_primary(documents: list[UploadedContent]) -> UploadedContent | None:
    return min(documents, key=_primary_rank, default=None)


def _primary_rank(document: UploadedContent) -> int:
    if document.upload.mime in XML_MIMES:
        return XML_PRIMARY_RANK
    if document.upload.mime == PDF_MIME:
        return PDF_PRIMARY_RANK
    return OTHER_PRIMARY_RANK


def ready_intake(
    archives: list[UploadedContent], documents: list[UploadedContent]
) -> EvidenceIntake:
    primary = select_primary(documents)
    if primary is None:
        return unreadable_intake([*archives, *documents])
    secondary_links = [
        EvidenceLink(file_id=document.upload.file_id, role=EvidenceRole.SECONDARY)
        for document in documents
        if document is not primary
    ]
    archive_links = [
        EvidenceLink(file_id=archive.upload.file_id, role=EvidenceRole.ARCHIVE)
        for archive in archives
    ]
    return EvidenceIntake(
        status=EvidenceIntakeStatus.READY,
        evidence=[
            EvidenceLink(file_id=primary.upload.file_id, role=EvidenceRole.PRIMARY),
            *secondary_links,
            *archive_links,
        ],
        primary_file_id=primary.upload.file_id,
        primary_sha256=sha256(primary.content).hexdigest(),
    )


def unreadable_intake(uploads: list[UploadedContent]) -> EvidenceIntake:
    flagged_file_id = uploads[0].upload.file_id if uploads else None
    return EvidenceIntake(status=EvidenceIntakeStatus.UNREADABLE, flagged_file_id=flagged_file_id)


def quarantined_intake(quarantined: UploadedContent) -> EvidenceIntake:
    is_threat = quarantined.upload.scan_status is FileScanStatus.THREAT
    return EvidenceIntake(
        status=EvidenceIntakeStatus.MALWARE if is_threat else EvidenceIntakeStatus.SCAN_FAILED,
        flagged_file_id=quarantined.upload.file_id,
    )
