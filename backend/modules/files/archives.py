import zipfile
from io import BytesIO
from pathlib import PurePosixPath

from contracts.files import EVIDENCE_MIME_BY_EXTENSION, ZIP_MIME
from contracts.mail_gateway import FetchedAttachment
from modules.files.errors import UnsafeArchiveError

ZIP_MAGIC = b"PK\x03\x04"
MAX_ARCHIVE_ENTRIES = 20
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 50 * 1024 * 1024
MAX_COMPRESSION_RATIO = 100
ARCHIVE_MEMBER_MIMES = {
    extension: mime for extension, mime in EVIDENCE_MIME_BY_EXTENSION.items() if mime != ZIP_MIME
}
IGNORED_MEMBER_PREFIXES = ("__MACOSX/", "/")


def is_zip(content: bytes) -> bool:
    return content.startswith(ZIP_MAGIC)


def expand_zip(content: bytes) -> list[FetchedAttachment]:
    try:
        with zipfile.ZipFile(BytesIO(content)) as archive:
            return _supported_members(archive)
    except (zipfile.BadZipFile, zipfile.LargeZipFile, RuntimeError, NotImplementedError) as error:
        raise UnsafeArchiveError("unreadable archive") from error


def _supported_members(archive: zipfile.ZipFile) -> list[FetchedAttachment]:
    entries = [entry for entry in archive.infolist() if _is_candidate_entry(entry)]
    if len(entries) > MAX_ARCHIVE_ENTRIES:
        raise UnsafeArchiveError("too many entries")
    members: list[FetchedAttachment] = []
    declared_total_bytes = 0
    for entry in entries:
        member_name = PurePosixPath(entry.filename).name
        member_mime = ARCHIVE_MEMBER_MIMES.get(PurePosixPath(member_name).suffix.lower())
        if member_mime is None:
            continue
        _reject_bomb_entry(entry)
        declared_total_bytes += entry.file_size
        if declared_total_bytes > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
            raise UnsafeArchiveError("archive too large")
        member_content = _read_bounded(archive, entry)
        members.append(
            FetchedAttachment(filename=member_name, mime=member_mime, content=member_content)
        )
    if not members:
        raise UnsafeArchiveError("no supported members")
    return members


def _is_candidate_entry(entry: zipfile.ZipInfo) -> bool:
    member_name = PurePosixPath(entry.filename).name
    is_hidden = member_name.startswith(".")
    is_ignored = entry.filename.startswith(IGNORED_MEMBER_PREFIXES)
    return not entry.is_dir() and not is_hidden and not is_ignored


def _reject_bomb_entry(entry: zipfile.ZipInfo) -> None:
    has_sizes = entry.file_size > 0 and entry.compress_size > 0
    is_over_compressed = has_sizes and entry.file_size / entry.compress_size > MAX_COMPRESSION_RATIO
    if is_over_compressed:
        raise UnsafeArchiveError("compression ratio too high")


def _read_bounded(archive: zipfile.ZipFile, entry: zipfile.ZipInfo) -> bytes:
    with archive.open(entry) as member_stream:
        member_content = member_stream.read(entry.file_size + 1)
    if len(member_content) > entry.file_size:
        raise UnsafeArchiveError("member larger than declared")
    return member_content
