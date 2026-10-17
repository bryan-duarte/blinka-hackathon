from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile, status

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
