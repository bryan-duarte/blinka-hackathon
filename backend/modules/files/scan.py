import asyncio

from contracts.files import FileScanStatus
from core.config import StorageSettings
from core.logging_config import get_logger
from modules.files.storage import StorageBackend

logger = get_logger(__name__)

SCAN_STATUS_TAG_KEY = "GuardDutyMalwareScanStatus"
SCAN_STATUS_BY_TAG_VALUE = {
    "NO_THREATS_FOUND": FileScanStatus.CLEAN,
    "THREATS_FOUND": FileScanStatus.THREAT,
    "UNSUPPORTED": FileScanStatus.UNSUPPORTED,
    "ACCESS_DENIED": FileScanStatus.FAILED,
    "FAILED": FileScanStatus.FAILED,
}


class MalwareScanService:
    def __init__(self, storage: StorageBackend, settings: StorageSettings) -> None:
        self._storage = storage
        self._settings = settings

    async def wait_for_scan(self, storage_key: str) -> FileScanStatus:
        if not self._settings.malware_scan_enabled:
            return FileScanStatus.DISABLED
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self._settings.scan_timeout_seconds
        while True:
            tags = await self._storage.object_tags(storage_key)
            tag_value = tags.get(SCAN_STATUS_TAG_KEY)
            if tag_value is not None:
                return SCAN_STATUS_BY_TAG_VALUE.get(tag_value, FileScanStatus.FAILED)
            if loop.time() >= deadline:
                logger.warning("malware_scan_timed_out", storage_key=storage_key)
                return FileScanStatus.FAILED
            await asyncio.sleep(self._settings.scan_poll_interval_seconds)
