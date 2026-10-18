import json
from typing import Protocol

import httpx
from aiobotocore.session import AioSession
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

from core.config import RealtimeSettings
from core.logging_config import get_logger
from modules.realtime.errors import RealtimePublishError

logger = get_logger(__name__)

APPSYNC_SIGNING_SERVICE = "appsync"
PUBLISH_TIMEOUT_SECONDS = 5
KEEPALIVE_EXPIRY_SECONDS = 15
PUBLISH_ATTEMPTS = 2
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
        self._session: AioSession | None = None
        self._http_client = httpx.AsyncClient(
            timeout=PUBLISH_TIMEOUT_SECONDS,
            limits=httpx.Limits(keepalive_expiry=KEEPALIVE_EXPIRY_SECONDS),
        )

    async def publish(self, channel: str, events: list[str]) -> None:
        body = json.dumps({"channel": channel, "events": events}).encode()
        headers = await self._signed_headers(body)
        try:
            response = await self._post_with_retry(body, headers)
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise RealtimePublishError from error
        failed_events = response.json().get("failed") or []
        if failed_events:
            logger.warning(
                "realtime_publish_partial", channel=channel, failed_count=len(failed_events)
            )

    async def _post_with_retry(self, body: bytes, headers: dict[str, str]) -> httpx.Response:
        for attempt in range(1, PUBLISH_ATTEMPTS):
            try:
                return await self._http_client.post(self._url, content=body, headers=headers)
            except httpx.TransportError:
                logger.info("realtime_publish_retried", attempt=attempt)
        return await self._http_client.post(self._url, content=body, headers=headers)

    def _aws_session(self) -> AioSession:
        if self._session is None:
            self._session = AioSession(profile=self._aws_profile)
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
