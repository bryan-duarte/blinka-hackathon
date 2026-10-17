from typing import Protocol

import aioboto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from modules.files.errors import StorageError

VIRTUAL_HOST_ADDRESSING = "virtual"


class StorageBackend(Protocol):
    async def put(self, key: str, content: bytes, content_type: str) -> None: ...

    async def get(self, key: str) -> bytes: ...

    async def delete(self, key: str) -> None: ...

    async def object_tags(self, key: str) -> dict[str, str]: ...


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
