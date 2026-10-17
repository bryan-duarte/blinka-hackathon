from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from modules.tools.service import ToolsService


class ToolsClient:
    def __init__(self, service: "ToolsService") -> None:
        self._service = service

    async def list_tools(self) -> list[str]:
        return []
