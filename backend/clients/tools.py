from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool

    from modules.tools.service import ToolsService


class ToolsClient:
    def __init__(self, service: "ToolsService") -> None:
        self._service = service

    def hello_world_tools(self) -> list["BaseTool"]:
        return self._service.hello_world_tools()
