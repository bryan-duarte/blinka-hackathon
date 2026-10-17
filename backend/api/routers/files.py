from typing import Annotated
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, Response, UploadFile, status

from api.deps import ClientsDep, CurrentUserDep
from contracts.files import FileUploadResult

files_router = APIRouter(prefix="/files", tags=["files"])

BYTES_PER_MEGABYTE = 1024 * 1024
MAX_UPLOAD_MEGABYTES = 25
MAX_UPLOAD_BYTES = MAX_UPLOAD_MEGABYTES * BYTES_PER_MEGABYTE
DEFAULT_UPLOAD_FILENAME = "upload"


@files_router.post("", response_model=FileUploadResult, status_code=status.HTTP_201_CREATED)
async def upload_file(
    user: CurrentUserDep,
    clients: ClientsDep,
    file: Annotated[UploadFile, File()],
) -> FileUploadResult:
    file_content = await file.read()
    if len(file_content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"file exceeds the {MAX_UPLOAD_MEGABYTES} MB limit",
        )
    return await clients.files.upload(
        user, file.filename or DEFAULT_UPLOAD_FILENAME, file.content_type or "", file_content
    )


@files_router.get("/{file_id}/content")
async def file_content(file_id: UUID, user: CurrentUserDep, clients: ClientsDep) -> Response:
    stored_content = await clients.files.read_cleared_bytes(user, file_id)
    encoded_filename = quote(stored_content.file.filename, safe="")
    return Response(
        content=stored_content.content,
        media_type=stored_content.file.mime,
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{encoded_filename}",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox",
            "Cache-Control": "private, no-store",
        },
    )
