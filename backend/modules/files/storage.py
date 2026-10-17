from typing import Protocol

import aioboto3
from botocore.exceptions import ClientError

from core.logging_config import get_logger
from modules.files.errors import StorageError

logger = get_logger(__name__)

HTTP_STATUS_NOT_FOUND = 404
BUCKET_ALREADY_OWNED_ERROR_CODE = "BucketAlreadyOwnedByYou"


class StorageBackend(Protocol):
    async def put(self, key: str, content: bytes, content_type: str) -> None: ...

    async def get(self, key: str) -> bytes: ...

    async def delete(self, key: str) -> None: ...

    async def ensure_bucket(self) -> None: ...


class ObjectStorageBackend:
    def __init__(
        self,
        endpoint_url: str,
        bucket: str,
        access_key_id: str,
        secret_access_key: str,
    ) -> None:
        self._bucket = bucket
        self._session = aioboto3.Session(
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
        )
        self._client_context = self._session.client("s3", endpoint_url=endpoint_url)
        self._client = None

    async def _object_client(self):
        if self._client is None:
            self._client = await self._client_context.__aenter__()
        return self._client

    async def put(self, key: str, content: bytes, content_type: str) -> None:
        client = await self._object_client()
        try:
            await client.put_object(
                Bucket=self._bucket, Key=key, Body=content, ContentType=content_type
            )
        except ClientError as error:
            raise StorageError from error

    async def get(self, key: str) -> bytes:
        client = await self._object_client()
        try:
            response = await client.get_object(Bucket=self._bucket, Key=key)
            async with response["Body"] as body:
                return await body.read()
        except ClientError as error:
            raise StorageError from error

    async def delete(self, key: str) -> None:
        client = await self._object_client()
        try:
            await client.delete_object(Bucket=self._bucket, Key=key)
        except ClientError as error:
            raise StorageError from error

    async def ensure_bucket(self) -> None:
        client = await self._object_client()
        try:
            await client.head_bucket(Bucket=self._bucket)
            return
        except ClientError as error:
            bucket_status = error.response["ResponseMetadata"]["HTTPStatusCode"]
            if bucket_status != HTTP_STATUS_NOT_FOUND:
                raise StorageError from error
        try:
            await client.create_bucket(Bucket=self._bucket)
        except ClientError as error:
            error_code = error.response.get("Error", {}).get("Code")
            if error_code != BUCKET_ALREADY_OWNED_ERROR_CODE:
                raise StorageError from error
        logger.info("storage_bucket_created", bucket=self._bucket)
