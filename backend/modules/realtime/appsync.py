import json
from typing import Protocol

import aioboto3
import httpx
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

from core.config import RealtimeSettings
from core.logging_config import get_logger
from modules.realtime.errors import RealtimePublishError

logger = get_logger(__name__)

APPSYNC_SIGNING_SERVICE = "appsync"
PUBLISH_TIMEOUT_SECONDS = 5
JSON_CONTENT_TYPE = "application/json"


class RealtimeBackend(Protocol):
    async def publish(self, channel: str, events: list[str]) -> None: ...


class NullRealtimeBackend:
    async def publish(self, channel: str, events: list[str]) -> None:
        return None


class AppSyncEventsBackend:
    def __init__(self, settings: RealtimeSettings) -> None:
        self._host = settings.http_domain
        self._url = f"https://{settings.http_domain}/event"
        self._region = settings.region
        self._aws_profile = settings.aws_profile or None
        self._session: aioboto3.Session | None = None

    async def publish(self, channel: str, events: list[str]) -> None:
        body = json.dumps({"channel": channel, "events": events}).encode()
        headers = await self._signed_headers(body)
        try:
            async with httpx.AsyncClient(timeout=PUBLISH_TIMEOUT_SECONDS) as http_client:
                response = await http_client.post(self._url, content=body, headers=headers)
                response.raise_for_status()
        except httpx.HTTPError as error:
            raise RealtimePublishError from error
        failed_events = response.json().get("failed") or []
        if failed_events:
            logger.warning(
                "realtime_publish_partial", channel=channel, failed_count=len(failed_events)
            )

    def _aws_session(self) -> aioboto3.Session:
        if self._session is None:
            self._session = aioboto3.Session(
                profile_name=self._aws_profile, region_name=self._region
            )
        return self._session

    async def _signed_headers(self, body: bytes) -> dict[str, str]:
        credentials = await self._aws_session().get_credentials()
        if credentials is None:
            raise RealtimePublishError("no aws credentials")
        frozen_credentials = await credentials.get_frozen_credentials()
        request = AWSRequest(
            method="POST",
            url=self._url,
            data=body,
            headers={"content-type": JSON_CONTENT_TYPE, "host": self._host},
        )
        SigV4Auth(frozen_credentials, APPSYNC_SIGNING_SERVICE, self._region).add_auth(request)
        return dict(request.headers.items())
