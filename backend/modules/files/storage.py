from typing import Protocol

import aioboto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from core.logging_config import get_logger
from modules.files.errors import StorageError, UnsafePrefixError

logger = get_logger(__name__)

VIRTUAL_HOST_ADDRESSING = "virtual"
DELETE_BATCH_SIZE = 1000
PREFIX_SEPARATOR = "/"


class StorageBackend(Protocol):
    async def put(self, key: str, content: bytes, content_type: str) -> None: ...

    async def get(self, key: str) -> bytes: ...

    async def delete(self, key: str) -> None: ...

    async def object_tags(self, key: str) -> dict[str, str]: ...

    async def delete_prefix(self, prefix: str) -> int: ...


class ObjectStorageBackend:
    def __init__(self, bucket: str, aws_profile: str | None, region: str) -> None:
        self._bucket = bucket
        self._session = aioboto3.Session(profile_name=aws_profile, region_name=region)
        self._client_context = self._session.client(
            "s3", config=Config(s3={"addressing_style": VIRTUAL_HOST_ADDRESSING})
        )
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
        except (ClientError, BotoCoreError) as error:
            raise StorageError from error

    async def get(self, key: str) -> bytes:
        client = await self._object_client()
        try:
            response = await client.get_object(Bucket=self._bucket, Key=key)
            async with response["Body"] as body:
                return await body.read()
        except (ClientError, BotoCoreError) as error:
            raise StorageError from error

    async def delete(self, key: str) -> None:
        client = await self._object_client()
        try:
            await client.delete_object(Bucket=self._bucket, Key=key)
        except (ClientError, BotoCoreError) as error:
            raise StorageError from error

    async def object_tags(self, key: str) -> dict[str, str]:
        client = await self._object_client()
        try:
            response = await client.get_object_tagging(Bucket=self._bucket, Key=key)
        except (ClientError, BotoCoreError) as error:
            raise StorageError from error
        return {tag["Key"]: tag["Value"] for tag in response.get("TagSet", [])}

    async def delete_prefix(self, prefix: str) -> int:
        is_scoped_prefix = prefix.endswith(PREFIX_SEPARATOR) and prefix != PREFIX_SEPARATOR
        if not is_scoped_prefix:
            raise UnsafePrefixError(prefix)
        client = await self._object_client()
        deleted_count = 0
        try:
            paginator = client.get_paginator("list_objects_v2")
            async for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
                keys = [{"Key": stored_object["Key"]} for stored_object in page.get("Contents", [])]
                for batch_start in range(0, len(keys), DELETE_BATCH_SIZE):
                    batch = keys[batch_start : batch_start + DELETE_BATCH_SIZE]
                    response = await client.delete_objects(
                        Bucket=self._bucket, Delete={"Objects": batch, "Quiet": True}
                    )
                    failed_keys = [failure["Key"] for failure in response.get("Errors", [])]
                    if failed_keys:
                        logger.warning(
                            "storage_prefix_delete_partial", prefix=prefix, failed=len(failed_keys)
                        )
                    deleted_count += len(batch) - len(failed_keys)
        except (ClientError, BotoCoreError) as error:
            raise StorageError from error
        return deleted_count
